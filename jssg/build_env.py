import fnmatch
import pathlib
import os
import shutil

from .execution_rule import ExecutionRule


def build(indir, outdir, rules, files="", filesys=None, listeners=None):
    """Build files in `indir` to `outdir` given a rule matching list `rules`.

    Arguments
    =========
        indir : (string) Path to source
        outdir : (string) Path to build directory
        rules : (list/tuple) rule matching list (see below)
        files : (string or list) : files to process (default: all in indir)
        filesys : (FileSystem object)
        listeners : (Map[string, Object]) Objects with `on_data_return` and/or `before_execute` methods

    The `rules` list is a list or tuple of tuples taking the form
        (MATCH_RULE, (PATHMAP, EXECUTIONRULE/FILEMAP))
    The MATCH_RULE is a glob string, or a tuple of glob strings. For each file,
    the first MATCH_RULE to match the file name is used to choose the appropriate
    PATHMAP and EXECUTIONRULE.

    The `files` list is a list of file names to process, or a string. If it
    is a string, it is interpreted as a subdirectory of `indir` to process.
    Therefore, the empty string gives the default behaviour of processing all files
    in `indir`.

    `listeners` are objects with on_data_return and/or `before_execute` methods.
    `on_data_return` must have the inputs (inf, outf, data). This gives the
    input file name, the output file name (relative to indir and outdir respectively),
    and the data output returned from the execution rule matched to `inf`.

    The `before_execute` method takes no arguments and takes after all listeners
    have been called with `on_data_return`. It returns an arbitrary value, which is
    inserted into a dict object mapping the listener names to these outputs. The resulting
    dict is passed as the `state` object to the executions produced by all execution
    rules.

    Listeners allow capture/observation of data as it gets processed via `on_data_return`,
    allowing aggregation, which can then be injected into the executions via the state
    parameter.
    """

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
    """Given a rule matching list and file list, yield (rule, file) pairs.

    That is, for every file, lookup the appropriate rule from the rule matching list.
    This is entirely lazy, and thus files may be a generator/any iterable, even if
    it can only be traversed once.
    """
    return ((_first_matching_rule(rules, f), f) for f in files)

def evaluate_rules(fs, rule_file_pairs, listeners=None):
    """Evaluate a sequence of (rule, file) pairs.

    Given (rule,file) pairs, like those yielded from `match_files_to_rules`,
    call all execution rules, and process the outputs, notifying listeners
    of data returns, and calling `before_execute` callbacks, so as to produce
    the list of all executions and the total exec_state.

    Returns
    =======
        (exec_state, executions)
    """
    dat, executions = zip(*_lazy_evaluate_rules(fs, rule_file_pairs))
    exec_state = {}
    if listeners:
        exec_state = _notify_listeners(dat, listeners)
    return exec_state, executions

def _lazy_evaluate_rules(fs, rule_file_pairs):
    for rule, f in rule_file_pairs:
        result = _execute_rule(fs, rule, f)
        if result is None:
            continue
        outf, (ex, data) = result

        yield (f, outf, data), ex

def _execute_rule(fs, rule, f):
    if rule is None: return None
    pm, rule = rule
    outf = pm(f)
    rule = ExecutionRule.wrap(rule)
    return outf, rule(fs, f, outf)


def _notify_listeners(inputs, listeners):
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
    """Recursively list all files in directory `d`.

    If rel_to is not passed, the files are returned relative to the input directory
    `d` itself.
    """
    if rel_to is None:
        rel_to = d

    for directory_path, _, file_names in os.walk(d):
        for fn in file_names:
            yield pathlib.Path(directory_path, fn).relative_to(rel_to).as_posix()

class FileSys:
    """Convenience wrapper for file operations.

    Is aware of source and build directories such that all operations are
    relative to these.
    """
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
