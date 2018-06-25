import os
import tempfile
from shutil import rmtree

import pytest

from .base import BaseTestPreprocessor
from ...preprocessors import CompileTestFunctions
from .. import create_code_cell
from nbformat.v4 import new_notebook
from textwrap import dedent

@pytest.fixture
def preprocessor():
    return CompileTestFunctions()


@pytest.fixture
def resources(request):
    return {
        'nbgrader': {
            'notebook': 'problem1',
            'assignment': 'ps1',
        }
    }


@pytest.fixture
def course_dir(request):
    path = tempfile.mkdtemp()

    def fin():
        rmtree(path)
    request.addfinalizer(fin)

    return path


@pytest.fixture
def temp_cwd(request, course_dir):
    orig_dir = os.getcwd()
    path = tempfile.mkdtemp()
    os.chdir(path)

    with open("nbgrader_config.py", "w") as fh:
        fh.write(dedent(
            """
            c = get_config()
            c.CourseDirectory.root = r"{}"
            """.format(course_dir)
        ))

    def fin():
        os.chdir(orig_dir)
        rmtree(path)

    request.addfinalizer(fin)

    return path


class TestCompileTestFunctions(BaseTestPreprocessor):

    def test_parse_test_funcs(self, preprocessor, resources, course_dir, temp_cwd):
        cell1 = create_code_cell()
        cell1.source = dedent(
            """
            ### BEGIN HIDDEN BLOCK
            def test_bar():
                pass
            
            ### END HIDDEN BLOCK
            
            def test_foo(bar):
                assert bar is True, 'bar must be true'
            
            def foo(bar):
                # YOUR SOLUTION
                test_foo(bar)
                
            foo(True)
            """
        ).strip()
        nb = new_notebook()
        nb.cells.append(cell1)

        nb, resources = preprocessor.preprocess(nb, resources)

        assignment_id = resources['nbgrader']['assignment']
        notebook_id = resources['nbgrader']['notebook']
        build_path = os.path.join(temp_cwd, 'release', assignment_id, 'tests')

        assert os.path.exists(build_path)
        assert os.path.exists(os.path.join(build_path, '{}.so'.format(notebook_id)))

        import_line = 'from tests.{} import *'.format(notebook_id)
        assert import_line in nb.cells[0].source.split("\n")[0]