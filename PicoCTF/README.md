# PicoCTF

Grouped by event year, then category:

```text
PicoCTF/
└── <year>/                    # e.g. 2024, or "practice" for picoGym-only
    └── <category>/            # web, crypto, forensics, reverse, binary, general
        └── <challenge-name>/
            ├── README.md
            └── images/
```

Create one with:

```bash
ctfw new picoctf "Cookies" --year 2021 --category web
```

Most PicoCTF challenges are single-step, so the **Privilege escalation**
section of the template can usually be dropped. Redact the `picoCTF{...}`
flag value (`ctfw lint` catches one that slips through), and only publish once
the event has ended.
