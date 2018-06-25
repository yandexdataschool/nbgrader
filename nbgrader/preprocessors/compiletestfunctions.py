import os
from distutils.core import run_setup
from shutil import rmtree

from traitlets import Unicode

from . import NbGraderPreprocessor

SETUP_FILE_TEMPLATE = '''
import os
import sysconfig
from distutils.core import setup
from distutils.extension import Extension
from Cython.Build import cythonize
from Cython.Distutils import build_ext

extensions = [Extension("{ext_name}", ["{filename}"])]


def get_ext_filename_without_platform_suffix(filename):
    name, ext = os.path.splitext(filename)
    ext_suffix = sysconfig.get_config_var('EXT_SUFFIX')

    if ext_suffix == ext:
        return filename

    ext_suffix = ext_suffix.replace(ext, '')
    idx = name.find(ext_suffix)

    if idx == -1:
        return filename
    else:
        return name[:idx] + ext


class BuildExtWithoutPlatformSuffix(build_ext):
    def get_ext_filename(self, ext_name):
        filename = super().get_ext_filename(ext_name)
        return get_ext_filename_without_platform_suffix(filename)

setup(
    name="{ext_name}",
    ext_modules=cythonize(extensions),
    cmdclass={{'build_ext': BuildExtWithoutPlatformSuffix}},
)
'''


class CompileTestFunctions(NbGraderPreprocessor):

    begin_block_delimiter = Unicode(
        "BEGIN HIDDEN BLOCK",
        help="The delimiter marking the beginning of hidden block"
    ).tag(config=True)

    end_block_delimiter = Unicode(
        "END HIDDEN BLOCK",
        help="The delimiter marking the end of hidden block"
    ).tag(config=True)

    hidden_block_lines = []

    def _process_hidden_blocks(self, cell):
        lines = cell.source.split("\n")

        new_lines = []
        in_block = False
        removed_block = False

        for line in lines:
            if self.begin_block_delimiter in line:
                if in_block:
                    raise RuntimeError(
                        "Encountered nested begin hidden block statements"
                    )

                in_block = True
                removed_block = True

            elif self.end_block_delimiter in line:
                in_block = False

            elif not in_block:
                new_lines.append(line)

            elif in_block:
                self.hidden_block_lines.append(line)

        if in_block:
            raise RuntimeError("No end hidden block statement found")

        cell.source = "\n".join(new_lines)

        return removed_block

    def preprocess(self, nb, resources):
        self.first_cell_code_index = -1
        self.hidden_block_lines = []

        nb, resources = super(CompileTestFunctions, self).preprocess(nb, resources)

        self.assignment_id = resources['nbgrader']['assignment']
        self.notebook_id = resources['nbgrader']['notebook']

        if self.hidden_block_lines:
            self.log.info(resources)

            orig_dir = os.getcwd()
            build_path = os.path.join('release',
                                      self.assignment_id, 'tests')

            filename = '{}.py'.format(self.notebook_id)

            os.makedirs(build_path, exist_ok=True)

            package_init_file = os.path.join(build_path, '__init__.py')
            if not os.path.exists(package_init_file):
                open(package_init_file, 'w').close()

            with open(os.path.join(build_path, filename), 'w') as fp:
                fp.write("\n".join(self.hidden_block_lines))

            with open(os.path.join(build_path, 'setup.py'), 'w') as fp:
                fp.write(SETUP_FILE_TEMPLATE.format(ext_name=self.notebook_id, filename=filename))

            # compile
            os.chdir(build_path)
            run_setup('setup.py', ['build_ext', '--inplace',])

            # cleanup
            rmtree('build', ignore_errors=True)
            os.remove('{}.c'.format(self.notebook_id))
            os.remove('{}.py'.format(self.notebook_id))
            os.remove('setup.py')

            # add imports to first cell
            cell = nb.cells[self.first_cell_code_index]
            cell.source = "from tests.{} import *\n".format(self.notebook_id) + cell.source

            os.chdir(orig_dir)

        return nb, resources

    def preprocess_cell(self, cell, resources, index):

        if self.first_cell_code_index < 0 and cell.cell_type == 'code':
            self.first_cell_code_index = index

        # remove hidden block regions
        removed_block = self._process_hidden_blocks(cell)

        return cell, resources
