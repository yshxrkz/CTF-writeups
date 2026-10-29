# Pickle Rick

| Field          | Value                                         |
| -------------- | --------------------------------------------- |
| **Platform**   | TryHackMe                                     |
| **Link**       | https://tryhackme.com/room/picklerick         |
| **Difficulty** | Easy                                          |
| **Category**   | Web, Linux                                    |
| **OS**         | Linux                                         |
| **Date**       | 2026-10-29                                    |
| **Tags**       | `web-enum` `info-disclosure` `command-execution` `sudo-misconfig` |

> **Spoiler policy:** Flags, passwords, and other secrets are redacted as
> `REDACTED`. Only publish writeups for content the platform allows
> (e.g. retired HackTheBox machines, ended PicoCTF events).

---

## Summary

A Rick and Morty themed web server where the goal is to find three "ingredients"
(flags). Credentials were leaked in two places on the website itself (an HTML
comment and `robots.txt`), and logging in gave access to a web "command panel"
that runs OS commands as the web server user. A weak blocklist on that panel was
easy to sidestep, and the web user had unrestricted passwordless `sudo`, which
made reading the final flag trivial.

**Attack chain:** `Port scan` → `Creds leaked in page source + robots.txt` →
`Command panel (OS command execution)` → `sudo NOPASSWD: ALL` → `root`

---

## Tools

| Tool       | Purpose                                         |
| ---------- | ----------------------------------------------- |
| `nmap`     | Port and service discovery                      |
| `gobuster` | Web directory and file brute-forcing            |
| Browser    | Viewing page source, logging in, using the panel |

---

## Enumeration

### Port scan

```bash
nmap -sC -sV -oN scans/initial.nmap <TARGET_IP>
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH (Ubuntu)
80/tcp open  http    Apache httpd (Ubuntu)
```

| Port | Service | Version | Notes                                   |
| ---- | ------- | ------- | --------------------------------------- |
| 22   | SSH     | OpenSSH | No creds yet; password auth looked disabled |
| 80   | HTTP    | Apache  | Main attack surface                     |

### Web (80/tcp)

**Home page source.** Viewing the source (`Ctrl+U`) showed an HTML comment
left by the developer with a username in it:

```html
<!--
    Note to self, remember username!
    Username: REDACTED
-->
```

**`robots.txt`.** Instead of crawler rules, it held a single odd-looking
string. That turned out to be the password.

```text
REDACTED
```

**Directory brute-force.** I looked for PHP pages because the server is Apache
and the room is web-focused:

```bash
gobuster dir -u http://<TARGET_IP> -w /usr/share/wordlists/dirb/common.txt -x php,txt,html
```

```text
/assets      (Status: 301)
/login.php   (Status: 200)
/portal.php  (Status: 302) --> login.php
/robots.txt  (Status: 200)
```

`portal.php` redirects to `login.php`, so there's an authenticated area.

---

## Exploitation

### Initial access: command panel

Logging in at `/login.php` with the username from the HTML comment and the
password from `robots.txt` led to `/portal.php`, a **"Command Panel"** that
runs whatever you type as a shell command on the server.

Confirming execution and context:

```text
whoami   → www-data
pwd      → /var/www/html
ls       → (lists the web root, including a text file with the first ingredient)
```

`cat` was blocked by the panel ("Command disabled"). The block was a simple
blocklist of command names, so another file reader worked:

```text
less <ingredient-file>.txt   → first ingredient
```

> Opening the file directly in the browser at `http://<TARGET_IP>/<file>.txt`
> also works, since it sits in the web root.

The second ingredient was in a user's home directory:

```text
ls -la /home/rick
less "/home/rick/second ingredients"   → second ingredient
```

### Privilege escalation: sudo misconfiguration

Checking what `www-data` could run with `sudo`:

```text
sudo -l
...
User www-data may run the following commands:
    (ALL) NOPASSWD: ALL
```

The web server user can run **any** command as root without a password, so no
exploit was needed:

```text
sudo ls /root            → shows the third ingredient file
sudo less /root/<file>   → third ingredient
```

---

## Flags

| Flag               | Location                          | Value      |
| ------------------ | --------------------------------- | ---------- |
| Ingredient 1       | `/var/www/html/<file>.txt`        | `REDACTED` |
| Ingredient 2       | `/home/rick/second ingredients`   | `REDACTED` |
| Ingredient 3       | `/root/<file>.txt`                | `REDACTED` |

---

## Lessons Learned

- **What worked:** Reading page source and `robots.txt` before brute-forcing.
  Both credentials were sitting on the site and took under a minute to find.
- **Where I got stuck:** `cat` being blocked. A blocklist only stops the exact
  names it lists; `less`, `more`, `head`, `tail`, `nl`, and `grep . <file>` all
  read files too.
- **Defensive takeaways:**
  - Never leave credentials in HTML comments or `robots.txt` (which is public
    and often the first thing attackers read).
  - A web feature that runs shell commands shouldn't exist. If it must,
    use an allowlist of exact commands, not a blocklist.
  - The web service account should never have `sudo` rights, let alone
    `(ALL) NOPASSWD: ALL`.
- **New to me:** Running `sudo -l` as the first privesc check. It's quick and
  catches the easy wins before reaching for automated scripts.

---

## References

- [TryHackMe: Pickle Rick](https://tryhackme.com/room/picklerick)
- [OWASP: OS Command Injection Defense Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html)
- [GTFOBins](https://gtfobins.github.io/), a reference for which binaries can read files or escalate under `sudo`
