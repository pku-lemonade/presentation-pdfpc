"""Adapt the installed Présentation script in memory; never write its bundle."""

import ast
import importlib
from pathlib import Path
import plistlib
import sys
import unicodedata

BUNDLE_ID = "fr.imag.iihm.blanch.osx-presentation"


class CompatibilityError(RuntimeError):
    pass


def check_runtime(script):
    """Check the bundled bindings and imported framework symbols without a GUI."""
    version = "%s.%s" % sys.version_info[:2]
    packages = script.parent.parent / "Resources" / "packages" / version
    if not packages.is_dir():
        raise CompatibilityError(
            "Upstream has no bundled PyObjC for Python %s. Use /usr/bin/python3 "
            "with a supported Apple Command Line Tools installation; do not "
            "substitute Homebrew Python or install packages into system Python." % version)
    sys.path.insert(0, str(packages))
    modules = {"objc", "Foundation", "UserNotifications", "AppKit", "Quartz",
               "WebKit", "JavaScriptCore", "AVFoundation", "CoreMedia"}
    try:
        for node in ast.parse(script.read_text()).body:
            if isinstance(node, ast.ImportFrom) and node.module in modules:
                module = importlib.import_module(node.module)
                for alias in node.names:
                    getattr(module, alias.name)
    except (ImportError, AttributeError, OSError) as error:
        raise CompatibilityError("Upstream macOS bindings cannot load: %s" % error) from error


def _module_stores(nodes):
    """Assignments in module control flow, excluding deferred function bodies."""
    class Stores(ast.NodeVisitor):
        def __init__(self):
            self.names = set()

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store):
                self.names.add(node.id)

        def visit_FunctionDef(self, node):
            pass

        visit_AsyncFunctionDef = visit_FunctionDef
        visit_ClassDef = visit_FunctionDef
        visit_Lambda = visit_FunctionDef

    visitor = Stores()
    for node in nodes:
        visitor.visit(node)
    return visitor.names


def find_upstream():
    for root in (Path("/Applications"), Path.home() / "Applications"):
        if not root.exists():
            continue
        for app in root.glob("*.app"):
            name = "".join(c for c in unicodedata.normalize("NFKD", app.name)
                           if not unicodedata.combining(c)).lower()
            if name != "presentation.app":
                continue
            try:
                info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
            except (OSError, ValueError):
                continue
            if info.get("CFBundleIdentifier") != BUNDLE_ID:
                continue
            if info.get("CFBundleExecutable") != "presentation.py":
                raise CompatibilityError("The installed app no longer uses presentation.py.")
            script = app / "Contents/MacOS/presentation.py"
            if script.is_file():
                return app, script, info
    raise CompatibilityError("Install Renaud Blanch's Présentation.app in Applications first.")


def adapt_source(source, filename):
    """Insert integration hooks using syntax nodes, preserving upstream code.

    The notes hook runs after annotation collection and before notes drawing.
    Reload is routed through the wrapper so pressing r retains the extension.
    Finder's initial executable open-file event is filtered for this launcher.
    Refuse unknown structure rather than launching with silently missing notes.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as error:
        raise CompatibilityError("The installed script needs a different Python version.") from error
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    required = {"cgpdf_get", "cgpdf_array2list", "cgpdf_stream2str", "exit_relaunch", "annotations"}
    if not required.issubset(functions):
        raise CompatibilityError("Upstream PDF/notes helpers have changed; update this wrapper.")
    assignments = {n.id for n in ast.walk(tree)
                   if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    if not {"_pdf", "pdf_notes", "beamer_notes", "page_count", "url"}.issubset(assignments):
        raise CompatibilityError("Upstream PDF/notes state has changed; update this wrapper.")
    hooks = [i for i, n in enumerate(tree.body)
             if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
             and isinstance(n.value.func, ast.Name) and n.value.func.id == "prepare_animations"
             and len(n.value.args) == 1 and isinstance(n.value.args[0], ast.Name)
             and n.value.args[0].id == "widgets"]
    renderers = [n for n in ast.walk(tree) if isinstance(n, ast.List)
                 and [x.id for x in n.elts if isinstance(x, ast.Name)] == ["pdf_notes", "beamer_notes"]
                 and len(n.elts) == 2]
    if len(hooks) != 1 or len(renderers) != 1:
        raise CompatibilityError("Upstream notes rendering has changed; update this wrapper.")
    hook_index = hooks[0]
    before = tree.body[:hook_index]
    after = tree.body[hook_index + 1:]
    if (not {"_pdf", "pdf_notes", "page_count", "url"}.issubset(_module_stores(before))
            or "pdf_notes" in _module_stores(after)
            or any(functions[name] not in before for name in required)
            or not any(renderers[0] in list(ast.walk(node)) for node in after)):
        raise CompatibilityError("Upstream notes initialization order has changed; update this wrapper.")
    delegates = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
                 and n.name == "DropApplicationDelegate"]
    if len(delegates) != 1:
        raise CompatibilityError("Upstream Finder file opening has changed; update this wrapper.")
    handlers = [n for n in delegates[0].body if isinstance(n, ast.FunctionDef)
                and n.name == "application_openFile_"]
    original_guard = ast.dump(ast.parse("filename != os.path.abspath(__file__)", mode="eval").body)
    guards = [n for handler in handlers for n in ast.walk(handler)
              if isinstance(n, ast.If) and ast.dump(n.test) == original_guard]
    if len(handlers) != 1 or len(guards) != 1:
        raise CompatibilityError("Upstream Finder executable filtering has changed; update this wrapper.")
    guards[0].test = ast.parse("__pdfpc_wrapper_accept_document__(filename)", mode="eval").body
    reload_function = functions["exit_relaunch"]
    if [arg.arg for arg in reload_function.args.args] != ["path", "page"]:
        raise CompatibilityError("Upstream reload arguments have changed; update this wrapper.")
    reload_function.body = ast.parse("return __pdfpc_wrapper_relaunch__(path, page)").body
    hook = ast.parse("__pdfpc_wrapper_attach__(globals())").body[0]
    ast.copy_location(hook, tree.body[hooks[0]])
    tree.body.insert(hooks[0] + 1, hook)
    ast.fix_missing_locations(tree)
    return compile(tree, filename, "exec")
