import os
import shutil
import fnmatch
import pathlib
import types

from . import jinja_utils

def mirror_path(fn):
    return fn

def replace_extensions(suff):
    def op(fn):
        path = pathlib.Path(fn)
        # remove suffixes
        while path.suffix:
            path = path.with_suffix('')
        return path.with_suffix(suff).as_posix()
    return op

def remove_internal_extensions(fn):
    pathobj = pathlib.Path(fn)
    op = replace_extensions(pathobj.suffix)
    return op(fn)

def relative_path(fn, directory):
    return pathlib.Path(fn).relative_to(directory).as_posix()

class PathMapper:
    def __init__(self, indir, outdir):
        self.indir = indir
        self.outdir = outdir

    def execute(self, op, fn):
        try:
            inpath, outpath = op(fn)
            return inpath, outpath
        # If it takes fn and returns an outfn, we get a value error
        # due to too many values to unpack!
        except ValueError:
            outfn = op(fn)
            return (pathlib.Path(self.indir, fn).as_posix(),
                    pathlib.Path(self.outdir, outfn).as_posix())


class FileSys:
    def copy(self, inf, outf):
        self.ensure_dir(outf)
        shutil.copy(inf, outf)

    def read(self, inf):
        return open(inf, 'r', encoding='utf-8').read()

    def write(self, outf, s):
        self.ensure_dir(outf)
        open(outf, 'w', encoding='utf-8').write(s)

    def ensure_dir(self, outf):
        loc = pathlib.Path(outf).parent
        if not loc.is_dir():
            loc.mkdir(parents=True)


def list_all_files(d, rel_to=None):
    if rel_to is None:
        rel_to = d

    for directory_path, _, file_names in os.walk(d):
        for fn in file_names:
            yield pathlib.Path(directory_path).joinpath(fn).relative_to(rel_to).as_posix()



class FileMapper:
    def __init__(self, filesys=None):
        self.filesys = filesys if filesys is not None else FileSys()

    def execute(self, op, inpath, outpath):
        try:
            op(self.filesys, inpath, outpath)
        # If it is a string func we get a TypeError due to too many args
        except TypeError as e:
            self.wrapped_execute(op, inpath, outpath)

    def wrapped_execute(self, op, inpath, outpath):
        s = self.filesys.read(inpath)
        outs = op(s)
        self.filesys.write(outpath, outs)


def copy_file(fs, inpath, outpath):
    fs.copy(inpath, outpath)




class BuildEnv:
    def __init__(self, pathmapper, filemapper=None):
        self.pathmapper = pathmapper
        self.filemapper = filemapper if filemapper is not None else FileMapper()

    @classmethod
    def default(cls, indir, outdir):
        return cls(PathMapper(indir, outdir))

    def execute(self, rp, fn):
        pm, fm = rp
        inf, outf = self.pathmapper.execute(pm, fn)
        self.filemapper.execute(fm, inf, outf)

    def build(self, rules, files):
        if isinstance(files, str):
            files = self.filemapper.filesys.list_all_files(files)
        for file in files:
            rule = first_matching_rule(rules, file)
            if rule is not None:
                self.execute(rule, file)


def first_matching_rule(rules, path, default=None):
    for (rule, result) in rules:
        if _match_single_rule(rule, path):
            return result
    return default

def _match_single_rule(rule, path):
    if isinstance(rule, str):
        result = fnmatch.fnmatch(path, rule)
        return result
    for r in rule:
        if _match_single_rule(r, path):
            return True
    return False
