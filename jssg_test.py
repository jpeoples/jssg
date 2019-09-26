import unittest
from jinja2 import Environment

import jssg as jssg



class TestBasicPathFunctions(unittest.TestCase):
    def test_mirror(self):
        path = 'some/path'
        mirrored = jssg.mirror_path(path)
        self.assertEqual(path, mirrored)

    def test_replace_extensions(self):
        path = 'path/abc.xyz.def'
        op = jssg.replace_extensions('.txt')
        res1 = op(path)
        self.assertEqual(res1, 'path/abc.txt')

    def test_remove_internal_extensions(self):
        path = 'path/abc.xyz.def'
        res = jssg.remove_internal_extensions(path)
        self.assertEqual('path/abc.def', res)

    def test_relative_path(self):
        infile = 'test/a.txt'
        self.assertEqual('a.txt', jssg.relative_path(infile, 'test'))
        with self.assertRaises(ValueError):
            jssg.relative_path(infile, 'foo')

    def test_remove_extensions(self):
        infile = 'test/a.txt'
        self.assertEqual('test/a', jssg.remove_extensions(infile))

class TestPathMapper(unittest.TestCase):

    def test_path_map_execute(self):
        op = jssg.mirror_path
        fn = 'test.txt'
        inf,outf = jssg.execute_path_map(op, fn, "src", "build")
        self.assertEqual('src/test.txt', inf)
        self.assertEqual('build/test.txt', outf)


    def test_path_mapper_execute_with_pathmap(self):
        def my_op(fn, indir, outdir):
            return 'abc.txt', 'def.txt'
        fn = 'test.txt'
        inf,outf = jssg.execute_path_map(my_op, fn, "src", "build")
        self.assertEqual('abc.txt', inf)
        self.assertEqual('def.txt', outf)
        






class MockFileSystem:
    def __init__(self):
        self.log = ''
        self.files = ['a.txt', 'b/c.txt', 'd/e/f.md']

    def copy(self, inf, outf):
        self.log += 'copy({}, {}) '.format(inf, outf)

    def read(self, f):
        self.log += 'read({}) '.format(f)
        return self.read_value

    def write(self, f, s):
        self.log += 'write({}) '.format(f)
        self.wrote_value = s


    
class TestFileOperations(unittest.TestCase):
    def setUp(self):
        self.filesys = MockFileSystem()

    def test_copy(self):
        inpath = 'abc/xyz'
        outpath = 'cba/zyx'
        jssg.copy_file(self.filesys, inpath, outpath)
        self.assertEqual('copy(abc/xyz, cba/zyx) ', self.filesys.log)


    def test_file_mapper_execute(self):
        inpath = 'abc/xyz'
        outpath = 'cba/zyx'
        filemaps = jssg.FileMapper(self.filesys)
        filemaps.execute(jssg.copy_file, inpath, outpath)
        self.assertEqual('copy(abc/xyz, cba/zyx) ', self.filesys.log)

    def test_file_mapper_execute_stringfn(self):
        def my_op(s):
            return s + s
        filemaps = jssg.FileMapper(self.filesys)
        inpath = 'src/jinja.txt'
        outpath = 'build/jinja.txt'
        self.filesys.read_value = 'string1'
        filemaps.execute(my_op, inpath, outpath)

        self.assertEqual('read(src/jinja.txt) write(build/jinja.txt) ', self.filesys.log)
        self.assertEqual('string1string1', self.filesys.wrote_value)


class TestJinjaFile(unittest.TestCase):
    def setUp(self):
        self.filesys = MockFileSystem()
        jenv = Environment()
        self.jinja_file = jssg.jinja_utils.JinjaFile(jenv, {'my_var': 10})

    def test_jinja_file_render(self):
        res = self.jinja_file.render("my_var = {{my_var}}")
        self.assertEqual("my_var = 10", res)

    def test_jinja_file_full_render(self):
        self.filesys.read_value = "my_var = {{my_var}}"
        self.jinja_file.full_render(self.filesys, "abc.txt", "def.txt")
        self.assertEqual(self.filesys.wrote_value, "my_var = 10")
        self.assertEqual("read(abc.txt) write(def.txt) ", self.filesys.log)

    def test_jinja_file_full_render_same_as_call(self):
        self.filesys.read_value = "my_var = {{my_var}}"
        self.jinja_file.full_render(self.filesys, "abc.txt", "def.txt")
        wrote_value = self.filesys.wrote_value 
        self.jinja_file(self.filesys, "abc.txt", "def.txt")
        self.assertEqual(self.filesys.wrote_value, wrote_value)
        self.assertEqual("read(abc.txt) write(def.txt) "*2, self.filesys.log)

    def test_add_immediate_context(self):
        self.filesys.read_value = "infile = {{infile}}"
        jinja_file = self.jinja_file.add_immediate_context(self.my_ctx)
        self.assertEqual(1, len(jinja_file.immediate_context))

    def test_immediate_context(self):

        self.filesys.read_value = "infile = {{infile}}"
        jinja_file = self.jinja_file.add_immediate_context(self.my_ctx)
        jinja_file.full_render(self.filesys, "abc.txt", "def.txt")
        self.assertEqual("infile = abc.txt", self.filesys.wrote_value)
        self.assertEqual("read(abc.txt) write(def.txt) ", self.filesys.log)

    def my_ctx(self, ctx, inf, outf, s):
        return {"infile": inf}

        

class TestBuildEnv(unittest.TestCase):
    def test_execute(self):
        buildenv = jssg.BuildEnv('a','b', jssg.FileMapper(MockFileSystem()))
        buildenv.execute((self.my_pm, self.my_fm), 'blah blah')
        self.assertEqual('abc.txt def.txt', self.infoutf)

    def my_pm(self, fn, indir, outdir):
        return 'abc.txt', 'def.txt'

    def my_fm(self, fs, inf, outf):
        self.infoutf = inf + ' ' + outf

    def my_fm_2(self, inf, outf):
        self.infoutf = inf + ' ' + outf

    def test_build(self):
        buildenv = jssg.BuildEnv('a','b', jssg.FileMapper(MockFileSystem()))
        rules = [
            ('*.txt', None),
            ('*.pdf', (self.my_pm, self.my_fm_2))
        ]

        buildenv.build(rules, ['a.pdf'])
        self.assertEqual('abc.txt def.txt', self.infoutf)









class TestOtherOperations(unittest.TestCase):
    def test_first_matching_rule(self):
        rules = [
            ('*.txt', 1),
            ('a/*.xyz', 2),
            (('*.xyz', '*.abc'), 3),
            ]
        self.assertEqual(1, jssg.first_matching_rule(rules, 'a/b/c/x.txt'))
        self.assertEqual(2, jssg.first_matching_rule(rules, 'a/c/x.xyz'))
        self.assertEqual(3, jssg.first_matching_rule(rules, 'b/c/x.xyz'))
        self.assertEqual(3, jssg.first_matching_rule(rules, 'b/c/x.abc'))
        self.assertIs(None, jssg.first_matching_rule(rules, 'totally_unrelated_file'))

if __name__=='__main__': unittest.main()