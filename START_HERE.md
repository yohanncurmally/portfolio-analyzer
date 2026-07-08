# Start Here

This is a tool that analyzes your investment portfolio. It connects **read-only**
to your brokerage (it can never place a trade or move money), pulls your holdings,
and produces an interactive dashboard plus a candid written analysis. Everything runs
on your own computer under your own broker login.

**You don't need to understand any of the technical steps.** There are just two parts:
get the files onto your computer, then let Claude do the rest.

---

## Step 1: Get the files onto your computer

Pick whichever describes you.

### If you're not technical (no GitHub account needed)

1. Click this link. It just downloads a zip file, no account or sign-in required:
   **https://github.com/yohanncurmally/portfolio-analyzer/archive/refs/heads/main.zip**
2. Open the downloaded file to unzip it. You'll get a folder called
   **`portfolio-analyzer-main`**.
3. Drag that folder somewhere easy to find, like your Desktop.

That's it. Skip to Step 2.

### If you're technical (you have git / a GitHub account)

Clone the repo wherever you keep projects:

```bash
git clone https://github.com/yohanncurmally/portfolio-analyzer.git
cd portfolio-analyzer
```

---

## Step 2: Let Claude set it up

1. Install **Claude Code** (or use the Claude desktop app's coding mode) if you don't
   have it: https://claude.com/claude-code
2. Open **the folder from Step 1** in Claude Code.
3. Type this and hit enter:

   > **Read SETUP_FOR_CLAUDE.md and set me up.**

Claude will run everything for you, one step at a time, and only stop to ask when it
needs something only you can do (like logging into your broker or clicking an
approval button). It supports **Robinhood, Interactive Brokers, and 20+ other
brokers**.

Once you're set up, you can just say **"analyze my portfolio"** any time. During setup
Claude will also offer to **tailor everything to your own strategy**: your thesis, how
concentrated you are, and how you use options (including if you *sell* premium), so the
dashboard and suggestions fit how you actually invest. You can do that then or later by
saying **"let's personalize this."**

---

## Want to see it first, with no broker?

You don't have to connect anything to try it. Just tell Claude:

> **Run it in demo mode first.**

It produces the full dashboard and written analysis on a fabricated sample portfolio.
Nothing is fetched from the network and no account is involved, so you can see exactly
what you're getting before connecting your own book.

---

*Everything stays on your computer. Your login and your holdings are never uploaded
or shared. Nothing here is financial advice; it's analysis.*
