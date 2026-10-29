# <Room / Machine / Challenge Name>

| Field          | Value                                             |
| -------------- | ------------------------------------------------- |
| **Platform**   | TryHackMe / HackTheBox / PicoCTF                  |
| **Link**       | <URL to the room, machine, or challenge>          |
| **Difficulty** | Easy / Medium / Hard / Insane                     |
| **Category**   | e.g. Web, Linux, Windows, Crypto, Forensics, Pwn  |
| **OS**         | Linux / Windows / N/A                             |
| **Date**       | YYYY-MM-DD                                        |
| **Tags**       | `tag1` `tag2` `tag3`                              |

> **Spoiler policy:** Flags, passwords, and other secrets are redacted as
> `REDACTED`. Only publish writeups for content the platform allows
> (e.g. retired HackTheBox machines, ended PicoCTF events).

---

## Summary

<!-- 2–4 sentences: what the target was, the path you took to compromise it,
     and the key weakness. Someone should be able to read only this section
     and know the attack chain. -->

**Attack chain:** `Recon` → `Foothold via ...` → `Privesc via ...`

---

## Tools

| Tool     | Purpose                         |
| -------- | ------------------------------- |
| `nmap`   | Port and service scanning       |
| `<tool>` | `<what you used it for>`        |

---

## Enumeration

### Port scan

```bash
nmap -sC -sV -oN scans/initial.nmap <TARGET_IP>
```

```text
<trimmed scan output: only the interesting lines>
```

| Port | Service | Version | Notes |
| ---- | ------- | ------- | ----- |
|      |         |         |       |

### <Service-specific enumeration, e.g. Web (80/tcp)>

<!-- What you looked at, what you found, and why it mattered.
     Include dead ends briefly; they're useful when you reread this later. -->

---

## Exploitation

### Initial access

<!-- The vulnerability or misconfiguration, how you confirmed it,
     and the steps to get a foothold. -->

### Privilege escalation

<!-- How you went from your initial user to root/SYSTEM (or the final goal).
     Skip this section for single-step challenges. -->

---

## Flags

| Flag        | Location          | Value      |
| ----------- | ----------------- | ---------- |
| User / Flag 1 | `/path/to/file` | `REDACTED` |
| Root / Flag 2 | `/path/to/file` | `REDACTED` |

---

## Lessons Learned

- **What worked:** <!-- technique or habit worth repeating -->
- **What I missed / where I got stuck:** <!-- and what finally unblocked you -->
- **Defensive takeaway:** <!-- how the target should have been configured -->
- **New to me:** <!-- tool, flag, or concept you learned -->

---

## References

- <Links to docs, CVEs, GTFOBins entries, blog posts you used>
