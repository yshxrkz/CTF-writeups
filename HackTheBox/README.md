# HackTheBox

Machines and challenges are kept separate:

```text
HackTheBox/
├── Machines/
│   └── <machine-name>/
│       ├── README.md
│       └── images/
└── Challenges/
    └── <category>/            # e.g. web, crypto, pwn, forensics
        └── <challenge-name>/
            ├── README.md
            └── images/
```

Create one with:

```bash
ctfw new hackthebox "Lame" --kind machine --difficulty easy
```

```bash
ctfw new hackthebox "Templated" --kind challenge --category web
```

Only publish writeups for **retired** machines and challenges. HackTheBox's
terms forbid sharing solutions for active content.
