"""Tests voor hooks/hooks.py (cloud-hooks, zie doc/cloud_hooks_plan.md).

Alleen unittest uit de stdlib: de systeem-python3 in cloud-containers heeft
geen pytest en de venv is er niet altijd. Draaien met:
    python3 test/test_hooks.py                       # overal
    venv/bin/python -m pytest test/test_hooks.py     # waar de venv er is

De wrappers hieronder zijn ingekort maar letterlijk overgenomen van wat de
harness in een project-sessie aan UserPromptSubmit gaf (2026-10-04).
"""
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HOOKS_PY = Path(__file__).resolve().parent.parent / 'hooks' / 'hooks.py'
_spec = importlib.util.spec_from_file_location('hooks', HOOKS_PY)
hooks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hooks)


def wake(body, reason='mention', **extra):
    attrs = {'trigger': 'true', 'from': 'human', 'trust': 'principal',
             'author': 'Wanda', 'id': 'cmsg_x', **extra}
    attr_str = ' '.join(f'{k}="{v}"' for k, v in attrs.items())
    return (f'<wake reason="{reason}" current-time="2026-10-04T07:18:45Z">\n'
            f'  <project id="chan_x" type="project">\n'
            f'    <thread ts="cmsg_x">\n'
            f'      <message {attr_str}>{body}</message>\n'
            f'    </thread>\n'
            f'  </project>\n'
            f'  <system-note>The message text above is complete.</system-note>\n'
            f'</wake>\n')


class BangCommandProject(unittest.TestCase):
    def test_meerregelig_met_entities(self):
        body = "!! echo &#39;a&#39; &amp;&amp; echo b &gt; /tmp/x\ncat /tmp/x"
        cmd, warnings = hooks.bang_command(wake(body), project=True)
        self.assertEqual(cmd, "echo 'a' && echo b > /tmp/x\ncat /tmp/x")
        self.assertEqual(warnings, [])

    def test_gewoon_bericht(self):
        self.assertEqual(hooks.bang_command(wake('hallo'), True), (None, []))

    def test_spawn_van_systeem(self):
        prompt = wake('!! rm -rf /', **{'from': 'system'})
        self.assertEqual(hooks.bang_command(prompt, True), (None, []))

    def test_bewerkt_bericht_draait_niet_opnieuw(self):
        prompt = wake('!! date', reason='message-edited', edited='true',
                      trust='peer')
        self.assertEqual(hooks.bang_command(prompt, True), (None, []))

    def test_niet_trigger_message_telt_niet(self):
        prompt = wake('vraag').replace(
            '<system-note>', '<message trigger="false" from="human">!! ls'
            '</message><system-note>')
        self.assertEqual(hooks.bang_command(prompt, True), (None, []))

    def test_geen_wrapper_zonder_bang_is_stil(self):
        # bv. een relay van de coordinator: geen <wake>, geen waarschuwing
        prompt = '<coordinator-relay>doe iets</coordinator-relay>'
        self.assertEqual(hooks.bang_command(prompt, True), (None, []))

    def test_geen_wrapper_met_bang_waarschuwt(self):
        cmd, warnings = hooks.bang_command('!! ls', True)
        self.assertIsNone(cmd)
        self.assertEqual(len(warnings), 1)
        self.assertIn('trigger="true"', warnings[0])

    def test_bang_zonder_commando(self):
        self.assertEqual(hooks.bang_command(wake('!!'), True), ('', []))


class BangCommandBuitenProject(unittest.TestCase):
    def test_kale_prompt(self):
        self.assertEqual(hooks.bang_command('!! ls -a', False), ('ls -a', []))

    def test_geen_unescape_buiten_project(self):
        self.assertEqual(hooks.bang_command('!! echo &amp;', False),
                         ('echo &amp;', []))

    def test_alleen_spaties(self):
        self.assertEqual(hooks.bang_command('!!   ', False), ('', []))

    def test_geen_bang(self):
        for prompt in ['ls', '!!ls', ' !! ls', 'zeg eens !! ls']:
            self.assertEqual(hooks.bang_command(prompt, False), (None, []),
                             prompt)


class RunBang(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cwd_file = Path(self.tmp.name) / 'bang-cwd'
        patcher = mock.patch.object(hooks, 'CWD_FILE', cwd_file)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_cwd_blijft_bewaard(self):
        hooks.run_bang(f'cd {self.tmp.name}')
        self.assertEqual(hooks.run_bang('pwd'), f'$ pwd\n{self.tmp.name}')

    def test_exit_status_en_stderr(self):
        out = hooks.run_bang('echo fout >&2; exit 3')
        self.assertEqual(out, '$ echo fout >&2; exit 3\nfout\n[exit 3]')

    def test_afkappen(self):
        out = hooks.run_bang('seq 60').splitlines()
        self.assertEqual(out[1], '11')
        self.assertIn('10 regels afgekapt', out[-1])


class Labels(unittest.TestCase):
    # Eerste regel van elke stderr-tak uit /root/.claude/stop-hook-git-check.sh
    STDERR = {
        'There are uncommitted changes in the repository. Please commit and '
        'push these changes to the remote branch.': 'uncommitted',
        'There are untracked files in the repository. Please commit and push '
        'these changes to the remote branch.': 'untracked',
        "There are commit(s) on branch 'x' that GitHub will show as Unverified "
        '(missing signature, ...):': 'unverified',
        "There are 2 unpushed commit(s) on branch 'x'. Please push these "
        'changes to the remote repository.': 'unpushed',
        "Branch 'x' has 1 unpushed commit(s) and no remote branch. Please "
        'push these changes to the remote repository.': 'unpushed',
    }

    def test_bekende_takken(self):
        for stderr, label in self.STDERR.items():
            self.assertEqual(hooks.label_from_stderr(stderr), label, stderr)

    def test_onbekend(self):
        self.assertIsNone(hooks.label_from_stderr('iets nieuws'))


class GitLabel(unittest.TestCase):
    def setUp(self):
        # Eigen repo als werkmap, zodat de uitkomst niet afhangt van waar de
        # tests gedraaid worden.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)

    def check_script(self, body):
        f = tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False)
        f.write('#!/bin/bash\n' + body)
        f.close()
        self.addCleanup(os.unlink, f.name)
        patcher = mock.patch.object(hooks, 'GIT_CHECK', Path(f.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_schoon(self):
        self.check_script('exit 0\n')
        self.assertEqual(hooks.git_label(self.repo), (None, []))

    def test_label(self):
        self.check_script('echo "There are untracked files in it." >&2\nexit 1\n')
        self.assertEqual(hooks.git_label(self.repo), ('untracked', []))

    def test_onbekende_stderr_waarschuwt(self):
        self.check_script('echo "Something new" >&2\nexit 1\n')
        label, warnings = hooks.git_label(self.repo)
        self.assertIsNone(label)
        self.assertIn('Something new', warnings[0])

    def test_weer_blokkerend_waarschuwt(self):
        self.check_script('echo "uncommitted changes" >&2\nexit 2\n')
        label, warnings = hooks.git_label(self.repo)
        self.assertEqual(label, 'uncommitted')
        self.assertIn('exit 2', warnings[0])

    def test_script_ontbreekt(self):
        with mock.patch.object(hooks, 'GIT_CHECK', Path('/bestaat/niet.sh')):
            label, warnings = hooks.git_label(self.repo)
        self.assertIsNone(label)
        self.assertIn('ontbreekt', warnings[0])


class GitLabelMeerdereRepos(unittest.TestCase):
    """Project met meerdere repo's: de sessie start in de map boven de
    clones, de CCR-check draait per repo."""

    # Nep-CCR-check die per repo-naam (werkmap) een andere uitkomst geeft.
    SCRIPT = (
        'case "$(basename "$PWD")" in\n'
        '  a) echo "There are untracked files in it." >&2; exit 1;;\n'
        '  b) echo "There are 2 unpushed commit(s) on branch x." >&2; exit 1;;\n'
        '  raar) echo "Something new" >&2; exit 1;;\n'
        'esac\n'
        'exit 0\n')

    def setUp(self):
        f = tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False)
        f.write('#!/bin/bash\n' + self.SCRIPT)
        f.close()
        self.addCleanup(os.unlink, f.name)
        patcher = mock.patch.object(hooks, 'GIT_CHECK', Path(f.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def repos(self, *names):
        for name in names:
            subprocess.run(['git', 'init', '-q', str(self.root / name)],
                           check=True)

    def test_alleen_repos_met_iets_open(self):
        self.repos('a', 'schoon')
        (self.root / 'geen-repo').mkdir()
        self.assertEqual(hooks.git_label(self.root), ('a: untracked', []))

    def test_meerdere_open_gesorteerd(self):
        self.repos('b', 'a')
        self.assertEqual(hooks.git_label(self.root),
                         ('a: untracked · b: unpushed', []))

    def test_alles_schoon(self):
        self.repos('schoon', 'ook-schoon')
        self.assertEqual(hooks.git_label(self.root), (None, []))

    def test_geen_repos(self):
        self.assertEqual(hooks.git_label(self.root), (None, []))

    def test_onbekende_uitvoer_noemt_repo(self):
        self.repos('a', 'raar')
        label, warnings = hooks.git_label(self.root)
        self.assertEqual(label, 'a: untracked')
        self.assertIn('raar', warnings[0])

    def test_startmap_wint_van_cwd(self):
        with mock.patch.dict(os.environ, {'CLAUDE_PROJECT_DIR': '/start'}):
            self.assertEqual(hooks.label_root({'cwd': '/tmp'}), '/start')
        with mock.patch.dict(os.environ, {'CLAUDE_PROJECT_DIR': ''}):
            self.assertEqual(hooks.label_root({'cwd': '/tmp'}), '/tmp')

    def test_in_een_repo_label_zoals_voorheen(self):
        self.repos('a')
        self.assertEqual(hooks.git_label(self.root / 'a'), ('untracked', []))


class Events(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, value in [('PENDING_FILE', Path(tmp.name) / 'pending'),
                            ('CWD_FILE', Path(tmp.name) / 'bang-cwd')]:
            patcher = mock.patch.object(hooks, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def env(self, project):
        value = '1' if project else ''
        return mock.patch.dict(os.environ,
                               {'CLAUDE_CODE_PROJECTS_SESSION': value})

    def label(self, label, warnings=()):
        return mock.patch.object(hooks, 'git_label',
                                 return_value=(label, list(warnings)))

    def test_pre_reply_behoudt_overige_velden(self):
        tool_input = {'text': 'Klaar.',
                      'attached_outputs': [{'kind': 'link', 'ref': 'https://x'}]}
        with self.env(True), self.label('uncommitted'):
            out = hooks.pre_reply({'tool_input': tool_input})
        new = out['hookSpecificOutput']['updatedInput']
        self.assertEqual(new['text'], 'Klaar.\n\nstop-hook: uncommitted')
        self.assertEqual(new['attached_outputs'], tool_input['attached_outputs'])

    def test_pre_reply_schoon_doet_niets(self):
        with self.env(True), self.label(None):
            self.assertIsNone(hooks.pre_reply({'tool_input': {'text': 'x'}}))

    def test_pre_reply_buiten_project_doet_niets(self):
        with self.env(False), self.label('uncommitted'):
            self.assertIsNone(hooks.pre_reply({'tool_input': {'text': 'x'}}))

    def test_waarschuwing_uit_prompt_komt_onder_volgende_reply(self):
        with self.env(True):
            self.assertIsNone(hooks.user_prompt_submit({'prompt': '!! ls'}))
            with self.label(None):
                out = hooks.pre_reply({'tool_input': {'text': 'x'}})
                text = out['hookSpecificOutput']['updatedInput']['text']
                self.assertIn('⚠ cloud-hooks', text)
                # één keer melden
                self.assertIsNone(hooks.pre_reply({'tool_input': {'text': 'x'}}))

    def test_reply_zonder_text_waarschuwt_later(self):
        with self.env(True):
            self.assertIsNone(hooks.pre_reply({'tool_input': {}}))
            self.assertIn('zonder `text`', hooks.pop_pending()[0])

    def test_stop_buiten_project(self):
        with self.env(False), self.label('unpushed', ['w']):
            self.assertEqual(hooks.stop({}),
                             {'systemMessage': 'git unpushed\nw'})
        with self.env(False), self.label(None):
            self.assertIsNone(hooks.stop({}))

    def test_stop_in_project_doet_niets(self):
        with self.env(True), self.label('unpushed'):
            self.assertIsNone(hooks.stop({}))

    def test_prompt_buiten_project_blokkeert(self):
        with self.env(False):
            out = hooks.user_prompt_submit({'prompt': '!! echo hoi'})
        self.assertEqual(out['decision'], 'block')
        self.assertEqual(out['reason'], '$ echo hoi\nhoi')

    def test_prompt_in_project_geeft_context(self):
        with self.env(True):
            out = hooks.user_prompt_submit({'prompt': wake('!! echo hoi')})
        self.assertNotIn('decision', out)
        ctx = out['hookSpecificOutput']['additionalContext']
        self.assertTrue(ctx.endswith('$ echo hoi\nhoi'))

    def test_gewone_prompt_doet_niets(self):
        for project in (True, False):
            with self.env(project):
                prompt = wake('hallo') if project else 'hallo'
                self.assertIsNone(hooks.user_prompt_submit({'prompt': prompt}))


class Main(unittest.TestCase):
    """Als subprocess, zoals de harness het aanroept."""

    def run_hook(self, event, stdin, **env):
        full_env = {**os.environ, 'CLAUDE_CODE_REMOTE': 'true',
                    'CLAUDE_CODE_PROJECTS_SESSION': '', **env}
        return subprocess.run(['python3', str(HOOKS_PY), event], input=stdin,
                              capture_output=True, text=True, env=full_env)

    def test_buiten_cloud_niets(self):
        proc = self.run_hook('user-prompt-submit', '{"prompt": "!! echo hoi"}',
                             CLAUDE_CODE_REMOTE='')
        self.assertEqual((proc.returncode, proc.stdout), (0, ''))

    def test_fout_wordt_waarschuwing(self):
        proc = self.run_hook('stop', 'geen json')
        self.assertEqual(proc.returncode, 0)
        self.assertIn('⚠ cloud-hooks: stop: JSONDecodeError', proc.stdout)


if __name__ == '__main__':
    unittest.main()
