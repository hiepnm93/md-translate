"""mdtrans command line: init, backends, digest, translate, verify, repair, assemble, run, status."""
import argparse
import sys
from fnmatch import fnmatch
from pathlib import Path

from mdtrans import backends, config, glossary
from mdtrans.assemble import assemble_file
from mdtrans.digest import digest_file
from mdtrans.repair import repair_file
from mdtrans.translate import translate_file
from mdtrans.verify import verify_file


def _ctx(args):
    cfg = config.load(Path(args.config) if args.config else config.find(Path.cwd()))
    backends.load_dotenv(cfg.root / ".env")
    langs = [args.lang] if getattr(args, "lang", None) else cfg.targets
    srcs = [s for s in config.sources(cfg)
            if not getattr(args, "only", None) or fnmatch(s.relative_to(cfg.root).as_posix(), args.only)]
    gloss = glossary.load(cfg.root / cfg.glossary if cfg.glossary else None)
    return cfg, langs, srcs, gloss


def _backend(args):
    if args.backend == "none":
        return None
    if args.backend:
        return backends.make(args.backend, args.model)
    ok = [c for c in backends.probe() if c["ok"]]
    if len(ok) == 1:
        print(f"backend: {ok[0]['spec']} (only one available)")
        return backends.make(ok[0]["spec"], args.model or ok[0]["model"])
    _print_backends()
    sys.exit("choose a backend with --backend <spec> [--model M]")


def _print_backends():
    cands = backends.probe()
    rec = next((c for c in cands if c["ok"]), None)
    for c in cands:
        mark = "★" if c is rec else ("✓" if c["ok"] else "✗")
        print(f"{mark} {c['spec']:<36} model={c['model'] or '-':<20} {c['detail']}")
    print(f"recommended: {rec['spec']}" if rec else "no backend available (see README: Backends)")


def _summary(rep: dict) -> str:
    return " ".join(f"{k}={rep[k]}" for k in ("ok", "fail", "needs_human", "untranslated") if rep.get(k))


def _write(cfg, src, lang, wd) -> str:
    try:
        text = assemble_file(wd)
    except ValueError as e:
        return f"not assembled ({e})"
    out = config.out_path(cfg, src, lang)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return f"→ {out.relative_to(cfg.root)}"


def cmd_init(args):
    p = Path(args.dir) / config.NAME
    if p.exists():
        sys.exit(f"{p} already exists")
    p.write_text(config.TEMPLATE, encoding="utf-8")
    print(f"wrote {p}; also add '.mdtrans/' to .gitignore")


def cmd_backends(args):
    try:
        backends.load_dotenv(config.find(Path.cwd()).parent / ".env")
    except FileNotFoundError:
        pass
    _print_backends()


def cmd_pipeline(args):
    cfg, langs, srcs, gloss = _ctx(args)
    steps = {"digest": {"digest"}, "translate": {"digest", "translate"}, "verify": {"verify"},
             "repair": {"repair"}, "assemble": {"assemble"},
             "run": {"digest", "translate", "repair", "assemble"}}[args.cmd]
    be = _backend(args) if steps & {"translate"} or args.cmd == "repair" else None
    bad = 0
    for lang in langs:
        rules = config.rules_text(cfg, lang)
        for src in srcs:
            rel = src.relative_to(cfg.root).as_posix()
            wd = digest_file(cfg, src, lang) if "digest" in steps else config.workdir_for(cfg, src, lang)
            if not wd.exists():
                print(f"{lang} {rel}: not digested")
                bad += 1
                continue
            msg = []
            if args.cmd == "digest":
                msg.append(f"{len(list((wd / 'units').glob('*.src.md')))} units")
            if "translate" in steps:
                done, failed = translate_file(wd, be, cfg, lang, gloss, rules, force=args.force)
                msg.append(f"translated {done}" + (f" ({failed} failed)" if failed else ""))
            rep = None
            if "repair" in steps:
                rep = repair_file(wd, be, cfg, lang, gloss, rules)
            elif "verify" in steps:
                rep = verify_file(wd, cfg, lang, gloss)
            if rep:
                msg.append(_summary(rep))
                bad += sum(u["status"] != "ok" for u in rep["units"].values())
                if args.cmd == "verify":
                    for uid, u in rep["units"].items():
                        if u["failures"]:
                            print(f"  {rel}#{uid}: {', '.join(u['failures'])}")
            if "assemble" in steps:
                msg.append(_write(cfg, src, lang, wd))
            print(f"{lang} {rel}: {' | '.join(msg)}")
    sys.exit(1 if bad and args.cmd in ("verify", "repair", "run") else 0)


def cmd_status(args):
    import json

    cfg, langs, srcs, _ = _ctx(args)
    for lang in langs:
        for src in srcs:
            rp = config.workdir_for(cfg, src, lang) / "report.json"
            rep = json.loads(rp.read_text()) if rp.exists() else {}
            print(f"{lang} {src.relative_to(cfg.root).as_posix():<50} {_summary(rep) or 'not verified'}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mdtrans", description=__doc__)
    ap.add_argument("--config", help="path to mdtrans.toml (default: search upward from cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="write a commented mdtrans.toml")
    p.add_argument("dir", nargs="?", default=".")
    p.set_defaults(fn=cmd_init)
    sub.add_parser("backends", help="list usable LLM backends and a recommendation").set_defaults(fn=cmd_backends)
    for name, hlp in [("digest", "split sources into units"), ("translate", "translate missing units"),
                      ("verify", "hard-check translated units"), ("repair", "mechanical + LLM repair"),
                      ("assemble", "write output files"), ("run", "digest → translate → repair → assemble"),
                      ("status", "show per-file report")]:
        p = sub.add_parser(name, help=hlp)
        p.add_argument("--lang", help="one target language (default: all targets)")
        p.add_argument("--only", help="glob on source path relative to config, e.g. 'book/0*.md'")
        p.add_argument("--backend", help="ssh:<host> | openai[:<url>] | claude-cli | none")
        p.add_argument("--model")
        p.add_argument("--force", action="store_true", help="retranslate units that already have output")
        p.set_defaults(fn=cmd_status if name == "status" else cmd_pipeline)
    args = ap.parse_args(argv)
    try:
        args.fn(args)
    except (FileNotFoundError, ValueError, backends.BackendError) as e:
        sys.exit(f"mdtrans: {e}")
