import pathlib

def mirror_path(fn):
    """Simply replicate the source path in the build directory"""
    return fn

def replace_extensions(fn, *, suff=None):
    """Replace all extensions with specified suffix"""
    if suff is None:
        raise ValueError("Argument `suff` cannot be None")

    path = pathlib.Path(fn)
    # remove suffixes
    while path.suffix:
        path = path.with_suffix('')
    return path.with_suffix(suff).as_posix()

def remove_extensions(fn):
    """Remove all extensions"""
    return replace_extensions(fn, suff="")

def remove_internal_extensions(fn):
    """Remove all extensions but the last"""
    pth = pathlib.Path(fn)
    return replace_extensions(pth, suff=pth.suffix)

def nice_url(fn):
    """Input files mapped to nice urls.

    That is, about.html in the input would be mapped to about/index.html
    """
    return pathlib.Path(remove_extensions(fn), "index.html").as_posix()

