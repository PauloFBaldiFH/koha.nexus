"""Consent diagnostics accept only the locked upstream field and safe values."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('dspace_browser_test', Path(__file__).resolve().parents[1] / 'tools/dspace_browser_test.py')
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)


class AgreementChanges(unittest.TestCase):
    def test_new_consent_is_identified(self):
        self.assertEqual(browser.agreement_changes([{'op':'add', 'path':'/metadata/dspace.agreements.end-user', 'value':[{'value':'true'}]}]), ('true',))

    def test_revocation_is_not_misreported_as_acceptance(self):
        self.assertEqual(browser.agreement_changes([{'op':'replace', 'path':'/metadata/dspace.agreements.end-user/0', 'value':{'value':'false'}}]), ('false',))

    def test_multiple_conflicting_writes_remain_visible(self):
        operations = [{'op':'replace', 'path':'/metadata/dspace.agreements.end-user/0', 'value':{'value':v}} for v in ('true','false')]
        self.assertEqual(browser.agreement_changes(operations), ('true','false'))

    def test_private_profile_fields_are_neither_returned_nor_mutated(self):
        operations = [{'op':'replace', 'path':'/password', 'value':'private-test-password'},
                      {'op':'replace', 'path':'/metadata/person.email', 'value':[{'value':'private@example.org'}]}]
        original = copy.deepcopy(operations)
        self.assertEqual(browser.agreement_changes(operations), ())
        self.assertEqual(operations, original)

    def test_unknown_shapes_are_ignored(self):
        for value in (None, {}, 'private profile text', [None, 42, []], [{'op':'add'}]):
            with self.subTest(value=type(value).__name__):
                self.assertEqual(browser.agreement_changes(value), ())

    def test_similar_field_names_do_not_match(self):
        for path in ('/metadata/dspace.agreements.end-user-secret', '/metadata/dspace.agreements.end-user/0/value'):
            self.assertEqual(browser.agreement_changes([{'op':'add','path':path,'value':{'value':'true'}}]), ())

    def test_removal_is_never_a_positive_acceptance(self):
        self.assertEqual(browser.agreement_changes([{'op':'remove','path':'/metadata/dspace.agreements.end-user','value':[{'value':'true'}]}]), ())

    def test_only_explicit_upstream_string_values_are_reported(self):
        for value in (True, False, None, 'private profile value', {}):
            self.assertEqual(browser.agreement_changes([{'op':'replace','path':'/metadata/dspace.agreements.end-user/0','value':{'value':value}}]), ())


class DockerRestart(unittest.TestCase):
    def setUp(self):
        path=Path(__file__).resolve().parents[1]/'tools/dspace_install_test.py'
        spec=importlib.util.spec_from_file_location('dspace_install_test',path)
        self.install=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.install)
    def test_a_still_healthy_previous_invocation_does_not_prove_restart(self):
        rt=Mock()
        def wait(label,predicate,timeout):
            self.assertEqual(timeout,360)
            self.assertFalse(predicate())
            self.assertFalse(predicate())
            self.assertTrue(predicate())
        rt.wait.side_effect=wait
        active='ActiveState=active\nSubState=running\nInvocationID='
        answers=[active+'old','',active+'old','ActiveState=activating\nInvocationID=new',active+'new']
        with patch.object(self.install.module,'command',side_effect=answers) as command:
            self.install.restart_docker(rt)
        self.assertEqual(command.call_args_list[1].args[0],['systemctl','--no-block','restart','docker'])
        rt.docker.assert_called_once_with('info','--format','{{.ServerVersion}}',timeout=15)
    def test_missing_invocation_does_not_issue_a_restart(self):
        with patch.object(self.install.module,'command',return_value='ActiveState=active') as command:
            with self.assertRaisesRegex(self.install.module.Refused,'no systemd invocation'):
                self.install.restart_docker(Mock())
        self.assertEqual(command.call_count,1)
    def test_failed_service_never_passes_even_with_a_new_invocation(self):
        rt=Mock();rt.wait.side_effect=lambda label,predicate,timeout:predicate()
        with patch.object(self.install.module,'command',side_effect=['InvocationID=old','','ActiveState=failed\nInvocationID=new\nResult=exit-code']):
            with self.assertRaisesRegex(self.install.module.Refused,'exit-code'):
                self.install.restart_docker(rt)
        rt.docker.assert_not_called()


if __name__ == '__main__': unittest.main()
