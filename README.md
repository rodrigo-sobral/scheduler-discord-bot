# 📅 Scheduler Discord Bot

A Discord bot that schedules messages to users and channels at specific times with delivery confirmations and message management.

![Scheduler Bot](assets/images/scheduler-bot.png)

## Features

- ⏰ **Schedule Messages** - Set delivery time and date for messages
- 🗣️ **Natural Language Time** - Use `tomorrow at 3pm`, `next Friday`, `in 2 hours` instead of HH:MM
- 👥 **Multiple Destinations** - Send to multiple users/channels in one message
- ✅ **Delivery Confirmations** - Get notified when messages are delivered
- 🗂️ **Message Management** - List, update, delete, duplicate, pause and resume pending messages
- 🔁 **Recurring Messages** - Repeat messages daily, weekly, or monthly
- 📁 **Templates** - Save reusable message presets and schedule them with `/tpl use`
- ⏸️ **Pause & Resume** - Suspend a pending message without deleting it
- 📜 **Delivery History** - View previously delivered messages
- 🌍 **Per-User Timezones** - Each user sets their own timezone; all times are interpreted and displayed accordingly
- 🖼️ **Rich Embeds** - Optionally attach a custom title, colour, and URL to any scheduled message
- 🚨 **Failure Alerts** - If a message fails to deliver, the full original content is DMed back to the sender
- 📊 **Reliable Queuing** - SQLite database with automatic retry on failures

## Discord Commands

| Command | Purpose |
|---------|----------|
| `/help` | Show all available commands and usage |
| `/sch` | Schedule a message (time, destinations, optional repeat, optional embed) |
| `/ls` | List pending messages with urgency colour-coding and Edit/Pause/Delete buttons |
| `/del` | Delete a pending message by queue position |
| `/mv` | Update a pending message field (content, destinations, time, date) |
| `/dup` | Clone a pending message with a new delivery time |
| `/pause` | Suspend a pending message without deleting it |
| `/resume` | Re-activate a paused message |
| `/tpl save` | Save a reusable message template (content + destinations) |
| `/tpl use` | Schedule a message from a saved template |
| `/tpl ls` | List all saved templates |
| `/tpl del` | Delete a saved template |
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
/sch "Alert" @user "in 2 hours" embed_title:"⚠️ Reminder" embed_color:"ff6b6b"

# Queue management
/ls
/del 0
/mv time 0 20:00
/dup 0 18:00
/pause 2
/resume 2

# Templates
/tpl save name:standup message:"Daily stand-up time!" destinations:"#general"
/tpl use name:standup time:"tomorrow 9am" repeat:Daily
/tpl ls
/tpl del name:standup

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

## Legal

- [Privacy Policy](docs/PRIVACY.md)
- [Terms of Use](docs/TERMS.md)
- [License](LICENSE)
