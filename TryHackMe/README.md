# TryHackMe

One folder per room, named with the room's URL slug:

```text
TryHackMe/
└── <room-slug>/
    ├── README.md   # the writeup (copied from templates/writeup-template.md)
    └── images/     # screenshots referenced from README.md
```

Example: `https://tryhackme.com/room/picklerick` → `TryHackMe/pickle-rick/`.

Create one with:

```bash
ctfw new tryhackme "Pickle Rick" --difficulty easy --category "Web, Linux"
```

TryHackMe asks that answers and flags for active rooms are not published, so
keep every flag and secret as `REDACTED`.
