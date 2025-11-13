import unittest
from subprocess import CompletedProcess

from tools.tasks.taskwatch.ghcli import GHCLI, _Runner


class FlakyRunner(_Runner):
    def __init__(self, plan):
        # plan is a list of (predicate, return CompletedProcess)
        self.plan = plan
        self.calls = []

    def run(self, args):
        self.calls.append(args)
        for pred, resp in list(self.plan):
            if pred(args):
                # pop from plan
                self.plan.remove((pred, resp))
                return resp
        # default fail
        return CompletedProcess(args, 1, '', 'fail')


class GHCLIRetryTests(unittest.TestCase):
    def test_retry_repo_name(self):
        # First two attempts fail, third succeeds
        def is_repo_view(a):
            return a[:3] == ['gh', 'repo', 'view']
        plan = [
            (is_repo_view, CompletedProcess(['gh'], 1, '', 'err1')),
            (is_repo_view, CompletedProcess(['gh'], 1, '', 'err2')),
            (is_repo_view, CompletedProcess(['gh'], 0, 'repo\n', '')),
        ]
        gh = GHCLI(runner=FlakyRunner(plan), retries=2)
        self.assertEqual('repo', gh.repo_name())

    def test_retry_comments_graphql_fallback_cli(self):
        # GraphQL fails; CLI fallback returns JSON comments
        def is_api(a):
            return a[:3] == ['gh', 'api', 'graphql']
        def is_issue_view(a):
            return a[:3] == ['gh', 'issue', 'view']
        def is_repo_view(a):
            return a[:3] == ['gh', 'repo', 'view']
        cli_json = '[{"createdAt":"2024-01-01T00:00:00Z","body":"## TASKS"}]\n'
        plan = [
            (is_repo_view, CompletedProcess(['gh'], 0, '{"owner":{"login":"me"}}\n', '')),
            (is_repo_view, CompletedProcess(['gh'], 0, '{"name":"repo"}\n', '')),
            (is_api, CompletedProcess(['gh'], 1, '', 'api fail')),
            (is_issue_view, CompletedProcess(['gh'], 0, cli_json, '')),
        ]
        gh = GHCLI(runner=FlakyRunner(plan), retries=1)
        out = gh.list_issue_comments(123)
        self.assertEqual(1, len(out))
        self.assertTrue(out[0]['body'].startswith('## TASKS'))

    def test_retry_items_graphql_fallback_cli(self):
        # GraphQL fails; CLI fallback returns items JSON
        def is_api(a):
            return a[:3] == ['gh', 'api', 'graphql']
        def is_item_list(a):
            return a[:3] == ['gh', 'project', 'item-list']
        items_json = '[{"id":"X","content":{"number":42},"fields":[]}]\n'
        plan = [
            (is_api, CompletedProcess(['gh'], 1, '', 'api fail')),
            (is_item_list, CompletedProcess(['gh'], 0, items_json, '')),
        ]
        # Create a dummy project object for call; only number/owner used for fallback
        from tools.tasks.taskwatch.ports import GHProject
        proj = GHProject(owner='me', number=1, id='PRJ1', title='P')
        gh = GHCLI(runner=FlakyRunner(plan), retries=1)
        items = gh.list_items(proj)
        self.assertEqual(42, items[0]['content']['number'])


if __name__ == '__main__':
    unittest.main()
