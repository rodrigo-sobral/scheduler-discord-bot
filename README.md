# 📅 Scheduler Discord Bot

A Discord bot that schedules messages to users and channels at specific times with delivery confirmations and message management.

![Scheduler Bot](assets/images/scheduler-bot.png)

## Features

- ⏰ **Schedule Messages** - Set delivery time and date for messages
- 🗣️ **Natural Language Time** - Use `tomorrow at 3pm`, `next Friday`, `in 2 hours` instead of HH:MM
- 👥 **Multiple Destinations** - Send to multiple users/channels in one message
- ✅ **Delivery Confirmations** - Get notified when messages are delivered
- 🗂️ **Message Management** - List, update, and delete pending messages
- 🔁 **Recurring Messages** - Repeat messages daily, weekly, or monthly
- 📜 **Delivery History** - View previously delivered messages
- 🌍 **Per-User Timezones** - Each user sets their own timezone; all times are interpreted and displayed accordingly
- 📊 **Reliable Queuing** - SQLite database with automatic retry on failures

## Discord Commands

| Command | Purpose |
|---------|----------|
| `/help` | Show all available commands and usage |
| `/sch` | Schedule a message (message, destinations, time, optional date, optional repeat) |
| `/ls` | List all pending scheduled messages with urgency colour-coding and Edit/Delete buttons |
| `/del` | Delete a pending message by queue position |
| `/mv` | Update a pending message field (content, destinations, time, date) |
| `/history` | View previously delivered messages |
| `/tz set` | Set your personal timezone (IANA name, e.g. `Europe/Lisbon`) |
| `/tz get` | Show your current timezone setting |

## Quick Examples

```
# Scheduling — structured or natural language time
/sch "Hello!" @user 15:30
/sch "Daily report" #general 09:00
/sch "Birthday reminder" @alice @bob 25/12 10:00
/sch "Stand-up reminder" #general "tomorrow at 9am"
/sch "Weekly sync" @team "next Monday 10:00" repeat:Weekly

# Queue management
/ls
/del 0
/mv time 0 20:00

# History
/history
/history 25

# Timezone
/tz set Europe/Lisbon
/tz get
```

## Documentation

- **[DEVELOPMENT.md](assets/docs/DEVELOPMENT.md)** - How to set up and run locally
- **[DEPLOYMENT.md](assets/docs/DEPLOYMENT.md)** - How to deploy to your infrastructure

---

**License**: MIT
