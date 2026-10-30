"""Contracts and exercise state transitions for the standalone staff guide."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from conftest import REPO

MANUAL = REPO / 'staff-manual'


def test_staff_guides_have_complete_source_backed_content():
    data = json.loads((MANUAL / 'lessons.json').read_text())
    assert data['language'] == 'en'
    assert len(data['source_archive_sha256']) == 64
    lessons = data['lessons']
    assert len(lessons) == 20
    assert len({l['id'] for l in lessons}) == len(lessons)
    for lesson in lessons:
        assert len(lesson['steps']) == 3
        assert all(lesson.get(k) for k in ('title', 'section', 'overview', 'warning', 'result', 'where'))
        assert lesson['source']['path'].startswith('modules/')
        assert lesson['source']['path'].endswith('.tt')
        assert len(lesson['source']['sha256']) == 64
        assert lesson['fields'] and len({f['label'] for f in lesson['fields']}) == len(lesson['fields'])
        assert all(f['example'] and f['hint'] for f in lesson['fields'])


def test_homepage_language_versions_link_to_the_english_staff_manual():
    pages = [REPO / 'index.html', *(REPO / 'languages').glob('*/index.html')]
    assert len(pages) == 23
    for page in pages:
        expected = 'staff-manual/' if page.parent == REPO else '../../staff-manual/'
        assert 'href="' + expected + '">Koha staff manual (English)</a>' in page.read_text()
        assert (page.parent / expected / 'index.html').resolve() == MANUAL / 'index.html'
    html = (MANUAL / 'index.html').read_text()
    assert '<html lang="en"' in html
    for asset in ('manual.js', 'manual.css', '../preview/assets/preview.css'):
        assert (MANUAL / asset).is_file()
    assert 'fictional' in html and 'simulation' in html


def test_every_exercise_validates_before_review_and_completion():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for simulator state tests')
    script = r'''
const assert = require('node:assert/strict');
const {Exercise} = require('./staff-manual/manual.js');
const data = require('./staff-manual/lessons.json');
for (const lesson of data.lessons) {
  const e = new Exercise(lesson);
  assert.equal(e.stage, 0);
  assert.equal(e.next().ok, true);
  assert.equal(e.next({}).ok, false);
  assert.equal(e.stage, 1);
  const values = Object.fromEntries(lesson.fields.map(f => [f.label,f.example]));
  assert.equal(e.next(values).ok, true);
  assert.equal(e.stage, 2);
  assert.deepEqual(e.values, values);
  e.back(); assert.equal(e.stage, 1);
  assert.equal(e.next(values).ok, true);
  assert.equal(e.next().message, lesson.result);
  assert.equal(e.stage, 3);
  e.next(); assert.equal(e.stage, 3);
}
'''
    run = subprocess.run([node, '-e', script], cwd=REPO, capture_output=True, text=True, timeout=15)
    assert run.returncode == 0, run.stderr
