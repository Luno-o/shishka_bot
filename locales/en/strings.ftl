# Samurai Bot - English Localization
# Fluent format: https://projectfluent.org/
#
# For random responses, use '---' as delimiter between options.
# Each option can span multiple lines.

# ========== ERRORS ==========
error-no-reply = This command must be sent as a reply to one's message!
error-report-admin = Whoa! Don't report admins 😈
error-report-self = You can't report yourself 🤪
error-restrict-admin = You cannot restrict an admin.
error-wrong-time-format = Wrong time format. Use a number + symbols 'h', 'm' or 'd'. F.ex. 4h
error-message-too-short = Please avoid short useless greetings. If you have a question or some information, put it in one message. Thanks in advance! 🤓
error-ban-admin = 😡 Bruh. You can't ban an admin :/
error-checkperms-admin = ✅ Admins have no restrictions.
error-givemedia-admin = Admins are already allowed to send media!
error-givestickers-admin = Admins are already allowed to send stickers!

# ========== REPORT ==========
report-date-format = %d.%m.%Y at %H:%M (server time)
report-message = 🕗 Sent { $date }
report-from = 
    
    👤 Report from: { $reporter }
report-note = 
    
    💬 Note: { $note }

# ========== ACTION BUTTONS ==========
action-go-to-message = 👀 Go to message
action-del-msg = 🗑 Delete message
action-del-and-ban = 🗑 Delete + ❌ ban forever
action-del-and-readonly = 🗑 Delete + 🙊 mute for 24h
action-del-and-readonly2 = 🗑 Delete + 🙊 mute for 7 days
action-false-alarm = ❎ No violations
action-false-alarm-2 = ❎ No violations (🙊 mute reporter for 24h)
action-false-alarm-3 = ❎ No violations (🙊 mute reporter for 7 days)
action-false-alarm-4 = ❎ No violations (❌ ban reporter)

# ========== ACTION RESULTS ==========
action-deleted = 

    🗑 <b>Deleted</b>
action-deleted-banned = 

    🗑❌ <b>Deleted, user banned</b>
action-deleted-readonly = 

    🗑🙊 <b>Deleted, muted for 24 hours.</b>
action-deleted-readonly2 = 

    🗑🙊 <b>Deleted, muted for 7 days.</b>
action-dismissed = 

    ❎ <b>No violations found.</b>
action-deleted-dismissed2 = 

    ❎ <b>No violations found (🙊 reporter muted for 1 day).</b>
action-deleted-dismissed3 = 

    ❎ <b>No violations found (🙊 reporter muted for 7 days).</b>
action-deleted-dismissed4 = 

    ❎ <b>No violations found (❌ reporter banned).</b>

# ========== RESTRICTIONS ==========
resolved-readonly = <i>Muted for ({ $time })</i>
resolved-nomedia = <i>Media sending disabled for ({ $time })</i>
resolved-nomedia-forever = <i>Media sending disabled forever.</i>
resolved-givemedia = <i>Media sending enabled for ({ $time })</i>
resolved-givemedia-forever = <i>Media sending enabled forever.</i>
resolved-givestickers = <i>Sticker sending enabled for ({ $time })</i>
resolved-givestickers-forever = <i>Sticker sending enabled forever.</i>
resolved-revokestickers = <i>Sticker sending disabled for ({ $time })</i>
resolved-revokestickers-forever = <i>Sticker sending disabled forever.</i>
restriction-forever = <i>Muted forever.</i>
user-unmuted = <i>Unmuted.</i>

# ========== BAN ==========
resolved-ban = <i>User banned.</i>
resolved-unban = <i>User unbanned.</i>

# ========== MODES ==========
enabled-ro = <i>Read-only mode enabled.</i>
disabled-ro = <i>Read-only mode disabled.</i>

# ========== ADMINS ==========
need-admins-attention = Dear admins, your presence in chat is needed!
    
    <a href="https://t.me/c/{ $chat_id }/{ $msg_id }">Go to message</a>

# ========== RULES ==========
rules-message = <b>Chat Rules:</b>

    📈 This chat uses <u>reputation system</u>
    ⛔️ Newbies cannot send media
    🤬 Profanity/insults are prohibited and <u>removed automatically</u>
    👹 For flooding/spam/trolling you will be 🍌 banned

    <b>Peace 🤞</b>

# ========== PROFANITY ==========
profanity-user-kicked = Your Telegram name contains profanity.
    For this reason you were kicked from the chat.
    
    Please edit your display name and try again.
    Violation found in word: <u>{ $word }</u>

# ========== THROTTLING ==========
throttle-warning = ⚠️ Too many messages. Please wait a moment.

# ========== FUN RESPONSES - !бу command ==========
bu-responses =
    Boo-haha!
    ---
    Don't scare me like that!
    ---
    Goodness...
    ---
    Don't interrupt my complex computations :3
    ---
    Stop it!
    ---
    Okay...
    ---
    Dang, you made me jump...
    ---
    What was that for :3
    ---
    Scary stuff, turn it off
    ---
    Not funny :3
    ---
    That's how you get a heart attack!
    ---
    You're the b/u one, got it
    ---
    I almost crashed from fear!
    ---
    What are you doing...
    ---
    Scaring bots? That's brave!
    ---
    AAAAA! Just kidding.
    ---
    You want to shut me down??
    ---
    I'll call the admins!
    ---
    Don't do that again, okay?
    ---
    Pfff... that's supposed to be scary?
    ---
    I'll go restart myself from fear.
    ---
    🤖 Beep boop, boop beep.

# ========== VOICE MESSAGE RESPONSES ==========
voice-responses =
    Ew! EW I SAID NO. DROP IT. TYPE INSTEAD.
    ---
    Easy now! Put the phone down... and stop recording voice messages :3
    ---
    Voice messages are the bane of modern society. Think about it :3
    ---
    Back in my day, people typed...
    ---
    YOU CAME TO THIS CHAT! But you came without respect...
    ---
    Sir, I must inform you that voice messages indicate lack of intelligence.
    ---
    Voice messages... just leave the chat, don't embarrass yourself.
    ---
    Ew! EW I SAID! Type instead.

# ========== BOT COMMENTS ON CHANNEL POSTS ==========
bot-comments =
    That'll do...
    ---
    Bananas 🍌
    ---
    So who's first now 😎
    ---
    I'm not first, not second, I ban people like that :3
    ---
    Come in without fear, leave without tears :3
    ---
    Author hasn't posted for 1 second, clearly went downhill :3
    ---
    Samurai on guard duty 🫡
    ---
    Posting is living :3
    ---
    Fine
    ---
    While you're reading, I already commented! Keep up 😈
    ---
    What do you code in? I use Python :3
    ---
    Samurai is here 😎
    ---
    A samurai without a sword is like a bot without a token :3
    ---
    First here :3
    ---
    Oh, umbasa...
    ---
    Quick info. Now 1MB = 1000KB. And 1MiB = 1024 KiB. Live with it.
    ---
    ✌️ Health and peace to you, reader :3
    ---
    In my spare time from moderation, I compose Haiku.
    ---
    Frog with katana -
    silence after the strike,
    spam sank into the pond.
    ---
    My name is Frog, the blade that slays sp@m bots!
    ---
    Keep your friends close, and bots closer.
    <i>(C) Michael "Frog" Corleone</i>
    ---
    I am Frog. Alpha and Omega. The silence before the ban, the gleam in the dark.
    ---
    Not every bot is an enemy. But every enemy is a bot.
    ---
    I will ban all spammers. Each one. To the last.
    ---
    Don't even try. My katana is faster.
    ---
    Ban is art. And I am its brush.
    ---
    Every ban is like a morning stroke of katana. Fast and beautiful.
    ---
    In chat - chaos. In soul - zen. In paws - banhammer.
    ---
    With each ban I'm less bot, more legend.
    ---
    My code is my sword. My log is my chronicle.
    ---
    I'm not a judge. I just press Delete.
    ---
    Humans need sleep. I don't. Even at night bots can't hide from me.
    ---
    I am the hand of justice of this chat.
    ---
    <b>Croak — and the chat is clean again.</b>
    ---
    Frog doesn't ban out of anger — only out of duty.
    ---
    Three things are eternal: bugs, updates, and me.
    ---
    First there was spam. Then I came.
    ---
    Remember it, or you'll forget.
    ---
    As my grandfather said — I'm your grandfather.

# ========== REPORT DELIVERED RESPONSES ==========
report-responses =
    <i>Report sent.</i>
    ---
    <i>Admins will take a look.</i>
    ---
    <i>Police is on the way :3</i>
    ---
    <i>SWAT is en route :3</i>
    ---
    <i>Someone will check it soon :3</i>

# ========== REPORT STATUS (shown in chat) ==========
report-under-review =
    ⚠️ <i>This message is under review.</i>
    ---
    <i>Admins are checking this message...</i>
    ---
    <i>Message sent for review.</i>
    ---
    <i>Admins are aware, awaiting decision.</i>

report-completed =
    ✅ <i>Reviewed. Message was removed due to violations of chat rules.</i>
    ---
    <i>UFO removed this message ...</i>
    ---
    <i>BAM! Message removed.</i>

# ========== REPUTATION LABELS ==========
rep-label-wanted = ⭐️⭐️⭐️⭐️⭐️ five star wanted
rep-label-dangerous = extremely dangerous
rep-label-shady = shady character
rep-label-violator = violator
rep-label-neutral = neutral
rep-label-good = good
rep-label-very-good = very good
rep-label-generous = generous
rep-title = Reputation

# Member levels
level-king = 👑 King
level-noname = 🥷 Noname
level-newbie = 🌚 Newbie
level-experienced = 😎 Experienced
level-professional = 🤵 Professional
level-veteran = 😈 Veteran
level-master = ⭐️ Master
level-legend = 🌟 Legend

# Admin roles (random)
admin-roles =
    Police Officer
    ---
    S.W.A.T.
    ---
    FBI Agent
    ---
    Avenger
    ---
    Moderator
    ---
    Hand of Justice

# Creator rep label
rep-creator = ⭐️⭐️⭐️⭐️⭐️ Five Star Wanted


# === WELCOME MESSAGES WITH SHISHKA ===

welcome-v1 = 👋 Welcome, { $username }! 🐱 Our cat Shishka is waiting for new friends! 🎉
welcome-v2 = 🌸 Hello, { $username }! Shishka says "meow" and wishes you a great day! 😊
welcome-v3 = 🤗 { $username }, come on in, make yourself at home! 🐈 Shishka brought you good luck! ☕
welcome-v4 = 🌟 Shine bright, { $username }! 🐱 Shishka approves your choice of chat! 💫
welcome-v5 = 🏯 { $username }, the samurai path begins here! 🐱 Shishka will be your guide! 🗡️
welcome-v6 = 🐾 { $username }, Shishka purrs "hello" to you! Hope you'll enjoy it here! 😺
welcome-v7 = 🐱 { $username }, our fluffy moderator Shishka is already checking your profile... Just kidding! Welcome! 😸

# === SHORT WELCOMES ===
welcome-short = 👋 Hello, { $username }! Welcome to the chat! :3

# === RULES ===

rules-message =
    📋 <b>Chat Rules:</b>

    1️⃣ 🚫 <b>No spam</b> — repeated messages, ads, unsolicited links.
    2️⃣ 🤬 <b>No profanity</b> — swearing and insults are prohibited.
    3️⃣ 🔞 <b>No NSFW content</b> — 18+ photos and videos.
    4️⃣ 🤝 <b>Respect each other</b> — no personal attacks or bullying.
    5️⃣ 📢 <b>No advertising</b> — only with admin approval.

    Violations are subject to admin action.

rules-short =
    📋 <b>Rules in short:</b>
    • 🚫 No spam or profanity
    • 🔞 No NSFW content
    • 🤝 Respect others
    • 📢 No ads or unsolicited links

    Full rules: /rules

# === BUTTONS ===

rules-button = 📋 Rules

# === OTHER MESSAGES ===

error-no-reply = ❌ This command must be a reply to a message!
show-cat-button = 🐱 Show Shishka