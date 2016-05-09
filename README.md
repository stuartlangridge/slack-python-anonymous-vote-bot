# Anonymous vote bot for Slack

A Slack bot to handle anonymous votes. Built as a plugin for [slackhq/python-rtmbot](https://github.com/slackhq/python-rtmbot).

Requires [my fork of rtmbot](https://github.com/stuartlangridge/python-rtmbot), until the changes are sent over and merged upstream.

Check out my fork of rtmbot and install it as per instructions. Then add anonvote.py from this repo to `plugins/anonvote/` in the rtmbot repo. Remember to invite the bot to a channel.

# How to vote

The bot manages anonymous, unanimous votes. To propose a vote, anyone can say `@vote on something` in a channel with the bot. The bot then sends a private message to each member of that channel asking them to vote. Each person votes by adding a :thumbsup: (yes) or :thumbsdown: (no) emoji reaction to the bot's DM. If everyone votes yes then the vote passes; if anyone votes no, the vote is declined. Who voted no is not revealed.

If the bot is addressed incorrectly in public then it will explain how to start votes. The bot's DM explains how to vote by adding an emoji reaction.
