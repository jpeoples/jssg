import fnmatch
import pathlib
import os
import shutil

from .execution_rule import ExecutionRule


def build(indir, outdir, rules, files="", filesys=None, listeners=None):
    """Build files in `indir` to `outdir` given a set of `rules`"""

    if filesys is None:
        filesys=FileSys(indir, outdir)

    if isinstance(files, str):
        files = filesys.list_all_files(files)

    rf_pairs = match_files_to_rules(rules, files)
    exec_state, executions = evaluate_rules(filesys, rf_pairs, listeners)

    for ex in executions:
        ex(exec_state)

# Given matching rules, compute
# a) A list of (inf, outf, data)
# b) executions

# Match files to rules does the first step, of selecting appropriate
# rules for each file
def match_files_to_rules(rules, files):
    return ((_first_matching_rule(rules, f), f) for f in files)

def evaluate_rules(fs, rule_file_pairs, listeners=None):
    dat, executions = zip(*lazy_evaluate_rules(fs, rule_file_pairs))
    exec_state = {}
    if listeners:
        exec_state = notify_listeners(dat, listeners)
    return exec_state, executions

def lazy_evaluate_rules(fs, rule_file_pairs):
    for rule, f in rule_file_pairs:
        outf, (ex, data) = execute_rule(fs, rule, f)
        yield (f, outf, data), ex



def translate_to_executions(fs, rules, files):
    data_returns = []
    executions = []
    for rule, f in match_files_to_rules(rules, files):
        outf, (ex, dat) = execute_rule(fs, rule, f)
        data_returns.append((f, outf, dat))
        executions.append(ex)
    return data_returns, executions


def execute_rule(fs, rule, f):
    if rule is None: return None
    pm, rule = rule
    outf = pm(f)
    rule = ExecutionRule.wrap(rule)
    return outf, rule(fs, f, outf)


def notify_listeners(inputs, listeners):
    for (inf, outf, dat) in inputs:
        if dat is not None:
            for l in listeners.values():
                if hasattr(l, 'on_data_return'):
                    l.on_data_return(inf, outf, dat)

    exec_state = {}
    for name, l in listeners.items():
        if hasattr(l, 'before_execute'):
            exec_state[name] = l.before_execute()

    return exec_state

def _first_matching_rule(rules, path, default=None):
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

def list_all_files(d, rel_to=None):
    if rel_to is None:
        rel_to = d

    for directory_path, _, file_names in os.walk(d):
        for fn in file_names:
            yield pathlib.Path(directory_path, fn).relative_to(rel_to).as_posix()

class FileSys:
    def __init__(self, indir, outdir):
        self.indir = indir
        self.outdir = outdir

    def resolve_in(self, inf):
        return pathlib.Path(self.indir, inf).as_posix()

    def resolve_out(self, outf):
        return pathlib.Path(self.outdir, outf).as_posix()


    def copy(self, inf, outf):
        self.ensure_dir(outf)
        shutil.copy(self.resolve_in(inf), self.resolve_out(outf))

    def read(self, inf):
        return open(self.resolve_in(inf), 'r', encoding='utf-8').read()

    def write(self, outf, s):
        self.ensure_dir(outf)
        open(self.resolve_out(outf), 'w', encoding='utf-8').write(s)

    def ensure_dir(self, outf):
        outf = self.resolve_out(outf)
        loc = pathlib.Path(outf).parent
        if not loc.is_dir():
            loc.mkdir(parents=True)

    def list_all_files(self, d=""):
        return list_all_files(self.resolve_in(d), rel_to=self.indir)
