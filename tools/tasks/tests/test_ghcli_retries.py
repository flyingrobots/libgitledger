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
            (is_repo_view, CompletedProcess(['gh'], 1, '', 'secondary rate limit')),
            (is_repo_view, CompletedProcess(['gh'], 1, '', 'secondary rate limit')),
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

    def test_list_issues_for_wave_cli_fallback(self):
        # GraphQL fails; gh issue list returns open issues numbers
        def is_api(a):
            return a[:3] == ['gh', 'api', 'graphql']
        def is_issue_list(a):
            return a[:3] == ['gh', 'issue', 'list']
        def is_repo_view(a):
            return a[:3] == ['gh', 'repo', 'view']
        issues_json = '[{"number": 7}, {"number": 8}]\n'
        plan = [
            (is_repo_view, CompletedProcess(['gh'], 0, '{"owner":{"login":"me"}}\n', '')),
            (is_repo_view, CompletedProcess(['gh'], 0, '{"name":"repo"}\n', '')),
            (is_api, CompletedProcess(['gh'], 1, '', 'graphql down')),
            (is_issue_list, CompletedProcess(['gh'], 0, issues_json, '')),
        ]
        gh = GHCLI(runner=FlakyRunner(plan), retries=0)
        out = gh.list_issues_for_wave(1)
        self.assertEqual([7,8], out)

    def test_malformed_cli_json_handled(self):
        # Comments CLI returns malformed JSON -> returns []
        def is_repo_view(a):
            return a[:3] == ['gh', 'repo', 'view']
        def is_api(a):
            return a[:3] == ['gh', 'api', 'graphql']
        def is_issue_view(a):
            return a[:3] == ['gh', 'issue', 'view']
        bad_json = '{this is not json\n'
        plan = [
            (is_repo_view, CompletedProcess(['gh'], 0, '{"owner":{"login":"me"}}\n', '')),
            (is_repo_view, CompletedProcess(['gh'], 0, '{"name":"repo"}\n', '')),
            (is_api, CompletedProcess(['gh'], 1, '', 'api fail')),
            (is_issue_view, CompletedProcess(['gh'], 0, bad_json, '')),
        ]
        gh = GHCLI(runner=FlakyRunner(plan), retries=1)
        out = gh.list_issue_comments(123)
        self.assertEqual([], out)

    def test_repo_owner_name_fail_returns_empty_lists(self):
        # When repo owner/name cannot be determined, list calls return [] gracefully
        def always_fail(a):
            return True
        plan = [
            (always_fail, CompletedProcess(['gh'], 1, '', 'err')),
        ]
        gh = GHCLI(runner=FlakyRunner(plan), retries=0)
        self.assertEqual([], gh.list_issue_comments(1))
        from tools.tasks.taskwatch.ports import GHProject
        proj = GHProject(owner='me', number=1, id='PRJ1', title='P')
        self.assertEqual([], gh.list_issues_for_wave(1))
        self.assertEqual([], gh.get_blockers(1))

    def test_get_blockers_pagination(self):
        # Two-page GraphQL result should be aggregated
        def is_repo_view(a):
            return a[:3] == ['gh', 'repo', 'view']
        def is_api(a):
            return a[:3] == ['gh', 'api', 'graphql']
        page1 = '{"data":{"repository":{"issue":{"blockedBy":{"pageInfo":{"hasNextPage":true,"endCursor":"CUR"},"nodes":[{"number":1},{"number":2}]}}}}}\n'
        page2 = '{"data":{"repository":{"issue":{"blockedBy":{"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[{"number":3}]}}}}}\n'
        plan = [
            (is_repo_view, CompletedProcess(['gh'], 0, '{"owner":{"login":"me"}}\n', '')),
            (is_repo_view, CompletedProcess(['gh'], 0, '{"name":"repo"}\n', '')),
            (is_api, CompletedProcess(['gh'], 0, page1, '')),
            (is_api, CompletedProcess(['gh'], 0, page2, '')),
        ]
        gh = GHCLI(runner=FlakyRunner(plan), retries=0)
        out = gh.get_blockers(999)
        self.assertEqual([1,2,3], out)


if __name__ == '__main__':
    unittest.main()
