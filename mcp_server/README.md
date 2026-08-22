# Qualys Container Security MCP — Quick Start for Non-Technical Users

This folder contains the **MCP server** that lets your AI assistant (Cursor) talk directly to your Qualys Container Security account.

You do not need to change any code. You only need to:

1. Copy the project to your computer.
2. Fill in your Qualys login details.
3. Point Cursor at the MCP server.

---

## What this gives you

Once connected, you can ask Cursor questions like:

- "List my running containers"
- "Show me images with critical vulnerabilities"
- "Which images have detected secrets or malware?"
- "List my Kubernetes pods in the prod namespace"

Cursor will call the Qualys API live and give you an answer.

---

## What you need before you start

- A Mac, Linux, or Windows computer with WSL
- Qualys Container Security API credentials (username, password, and platform URL)
- The Cursor code editor installed
- Your administrator or the person who set up this project should give you the repo URL

---

## Step 1: Install Python and Git

### On a Mac

1. Open **Terminal** (press `Cmd + Space`, type `Terminal`, press Enter).
2. Check if Python is installed:

   ```bash
   python3 --version
   ```

   If you see a version number like `Python 3.11.x`, you are good. If not, install Python from https://www.python.org/downloads/.

3. Check if Git is installed:

   ```bash
   git --version
   ```

   If it says `command not found`, install Git from https://git-scm.com/download/mac.

---

## Step 2: Copy the project to your computer

1. In Terminal, run:

   ```bash
   cd Documents
   git clone <repo-url-from-your-admin>
   cd qualys-container-security-mcp
   ```

2. Install the MCP server dependencies:

   ```bash
   pip3 install -r mcp_server/requirements.txt
   ```

---

## Step 3: Add your Qualys credentials

1. In the project folder, make a copy of the example settings file:

   ```bash
   cp .env.example .env
   ```

2. Open `.env` in a text editor (for example, `open -e .env` on a Mac, or right-click and open with Notepad).

3. Fill in the values your administrator gave you:

   ```env
   QUALYS_USERNAME=your-qualys-username
   QUALYS_PASSWORD=your-qualys-password
   QUALYS_PLATFORM_URL=https://gateway.qg2.apps.qualys.com
   ```

   You do not need to fill in the AWS/Bedrock section for the MCP server; those are only for the web chat.

4. **Save the file and close it.**

   The `.env` file is already set to be ignored by Git, so your password will not be accidentally shared.

---

## Step 4: Tell Cursor about the MCP server

1. Open **Cursor**.
2. Open the command palette (`Cmd + Shift + P` on Mac, `Ctrl + Shift + P` on Windows/Linux).
3. Type **MCP** and choose **Open MCP Settings**.
4. Paste this block, but replace the path with the full path to `mcp_server/server.py` on your computer:

   ```json
   {
     "mcpServers": {
       "qualys-cs": {
         "command": "python3",
         "args": [
           "/Users/yourname/qualys-container-security-mcp/mcp_server/server.py"
         ]
       }
     }
   }
   ```

5. Save the file.

---

## Step 5: Test it

1. Open a new chat in Cursor.
2. Type:

   ```
   List my running containers
   ```

3. Cursor should show it is using the `qualys-cs` MCP tools and then return a list from your Qualys account.

If it does not work, see the troubleshooting section below.

---

## Troubleshooting

### "command not found: python3"

Install Python from https://www.python.org/downloads/ and try again.

### "ModuleNotFoundError" or missing packages

Run the install command again:

```bash
pip3 install -r mcp_server/requirements.txt
```

### Cursor says the MCP server is not running

- Make sure the path in your Cursor MCP settings points exactly to `mcp_server/server.py`.
- Make sure the `.env` file exists in the project root (the same folder as `start.sh` and `stop.sh`).
- Make sure `QUALYS_USERNAME`, `QUALYS_PASSWORD`, and `QUALYS_PLATFORM_URL` are filled in.

### "401 Unauthorized" or "403 Forbidden"

Your Qualys username or password is wrong, or your account does not have Container Security API access. Contact your Qualys administrator.

---

## Updating to the latest version

When the project owner makes improvements, run this to get the latest code:

```bash
cd /Users/yourname/qualys-container-security-mcp
git pull
```

Then repeat Step 2 if new dependencies were added.
