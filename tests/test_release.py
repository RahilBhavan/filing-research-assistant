import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def test_package_metadata_and_ci_are_present(self):
        metadata=(ROOT/'setup.cfg').read_text()
        self.assertIn('name = filing-research-assistant',metadata)
        self.assertIn('filing-research = filing_assistant.__main__:main',metadata)
        self.assertIn('python-version: ["3.9", "3.12"]',(ROOT/'.github/workflows/ci.yml').read_text())

    def test_static_interface_has_accessible_labels_and_landmarks(self):
        html=(ROOT/'filing_assistant/static/index.html').read_text()
        for value in ['<main>', '<header>', '<label>Company<select', '<label>Filing<select', '<label>Section<select', 'for="question"', 'aria-live="polite"', '<dialog']:
            self.assertIn(value,html)

    def test_refresh_workflow_requires_contact_secret_and_artifact_review(self):
        workflow=(ROOT/'.github/workflows/refresh-sec.yml').read_text()
        self.assertIn('secrets.SEC_USER_AGENT',workflow)
        self.assertIn('actions/upload-artifact@v4',workflow)
        self.assertIn('refreshed-sec-corpus',workflow)

    def test_review_sheet_is_explicitly_independent(self):
        guide=(ROOT/'evaluation/HUMAN-REVIEW.md').read_text()
        self.assertIn('other than the person who implemented retrieval',guide)
        self.assertTrue((ROOT/'work/create_review_sheet.py').exists())

    def test_load_test_does_not_contain_credentials(self):
        script=(ROOT/'work/load_test.py').read_text()
        self.assertNotIn('SEC_USER_AGENT',script)
        self.assertIn('ThreadPoolExecutor',script)


if __name__=='__main__':
    unittest.main()
