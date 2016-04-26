outputs = []
get_slack = None
me = {}
votes_in_progress = {}

pending_replies = {}
def add_pending_reply(message, callback, *args, **kwargs):
    k = pending_replies.keys()
    if k:
        nextkey = max(k) + 1
    else:
        nextkey = 1
    pending_replies[nextkey] = {
        "message": message, "callback": callback, "args": args, "kwargs": kwargs
    }
    return nextkey

def process_untyped_data(data):
    pending_id = data.get("reply_to")
    if pending_id:
        pending = pending_replies.get(pending_id)
        if pending:
            del pending_replies[pending_id]
            pending["callback"](data, pending["message"], *pending["args"], **pending["kwargs"])

def catch_all(data):
    if data.get("type") in [None, "pong", "reconnect_url"]: return
    #print "Blimey, got data", data

def handle_error(exc_info):
    import traceback
    print "Got exception"
    traceback.print_exception(exc_info[0], exc_info[1], exc_info[2])

def process_hello(data):
    global get_slack, me
    me = get_slack().api_call("auth.test")

def receive_pending_reply(data, message, *args, **kwargs):
    print "Received pending reply to", message, args, kwargs
    votes_in_progress[kwargs["ask_about"]]["votes"][kwargs["member"]]["ts"] = data["ts"]
    print "rpr, vip is", votes_in_progress

def ask_users(channel, ask_about):
    global get_slack, votes_in_progress
    slack = get_slack()
    cinfo = slack.api_call("channels.info", channel=channel)
    vote_items = {}
    for member in cinfo["channel"]["members"]:
        if member == me["user_id"]: continue
        chat = slack.api_call("im.open", user=member)
        message = ("Please vote on whether *%s* should be invited. "
            "This vote is anonymous and unanimous; if everyone agrees, then "
            "a channel admin will invite them; if anyone disagrees, they will be "
            "declined, but nobody will know who disagreed or how many people did. "
            "Vote by adding an emoji reaction to _this_ message; add :thumbsup: "
            "(search for _thumbsup_) for "
            "\"_yes, invite them_\" or :thumbsdown: (search for _thumbsdown_) "
            "for _\"no, don't invite them\"_.") % (ask_about,)
        message_json = {
            "type": "message", 
            "channel": chat["channel"]["id"], 
            "text": message,
            "id": add_pending_reply(message, receive_pending_reply, 
                ask_about=ask_about, member=member, chat=chat)
        }
        slack.server.send_to_websocket(message_json)
        vote_items[member] = {"ts": None, "vote": None}
    votes_in_progress[ask_about] = {"votes": vote_items, "channel": channel}
    print "Have set votes in progress to", votes_in_progress

def process_reaction_added(data):
    print "in PRA"
    if data["reaction"] not in ["+1", "-1"]:
        outputs.append([data["item"]["channel"], "(sorry, only :+1: and :-1: emojis allowed)"])
        return

    dellist = []
    for name, votedata in votes_in_progress.items():
        channel = votedata["channel"]
        agreed = True
        rejected = False
        found = False
        for member, results in votedata["votes"].items():
            if results["ts"] == data["item"]["ts"]:
                results["vote"] = data["reaction"]
                found = True
            if results["vote"] is None:
                agreed = False
            elif results["vote"] == "-1":
                rejected = True
        if found:
            if rejected:
                outputs.append([channel, "The vote on *%s* is declined." % (name,)])
                dellist.append(name)
            elif agreed:
                outputs.append([channel, "The vote on *%s* is passed! Invite them!" % (name,)])
                dellist.append(name)
            else:
                print "Had a vote on", name, "but we're not complete yet:", votedata["votes"]
    for n in dellist: del votes_in_progress[n]


def process_message(data):
    global me, outputs, get_slack

    if not data.get("text"): return

    # Handle people replying to the bot with emoji rather than properly doing a reaction
    # Note that we don't have the final : on the thumbs emoji so that we catch
    # skintone variants
    if ":+1" in data["text"] or ":-1:" in data["text"] or ":thumbsup" in data["text"] or ":thumbsdown" in data["text"]:
        print "looks like an emoji IM"
        if data["channel"].startswith("D"):
            print "looks like an emoji IM in a chat window"
            if ":+1:" in data["text"] or ":thumbsup" in data["text"]:
                reaction = "+1"
            else:
                reaction = "-1"
            if len(votes_in_progress.keys()) == 1:
                # fake up a vote on the one outstanding
                print "1 vote ongoing: faking up a vote"
                ts = None
                votedname = None
                for name, v in votes_in_progress.items():
                    for m, results in v["votes"].items():
                        if m == data["user"]:
                            ts = results["ts"]
                            votedname = name
                if not ts:
                    print "ERROR: got an emoji IM (not reaction) from someone unexpected", data
                    return
                process_reaction_added({
                    "reaction": reaction,
                    "item": {
                        "channel": data["channel"],
                        "ts": ts
                    }
                })
                message_json = {
                    "type": "message", 
                    "channel": data["channel"],
                    "text": "Your vote on *%s* is accepted!" % (votedname,)
                }
                get_slack().server.send_to_websocket(message_json)
                return
            elif len(votes_in_progress.keys()) == 0:
                print "no votes ongoing; ignored"
                return
            else:
                print "Multiple votes ongoing; chastising"
                chastise = ("You need to vote by adding an "
                    "_emoji reaction_ to my message naming a person to vote on, not "
                    "by just replying with an emoji. "
                    "This is because there is more than one vote ongoing, and "
                    "I don't know which of them your vote applies to. See "
                    "https://get.slack.help/hc/en-us/articles/206870317-Emoji-reactions "
                    "for how to use emoji reactions.")

                message_json = {
                    "type": "message", 
                    "channel": data["channel"],
                    "text": chastise
                }
                get_slack().server.send_to_websocket(message_json)
                return

    # Handle people asking to start a vote in the main channel
    startsme = "<@%s> " % (me["user_id"],)
    if data["text"].startswith(startsme):
        voteon = "%son " % (startsme,)
        if data["text"].startswith(voteon):
            name = data["text"][len(voteon):]
            outputs.append([data["channel"], ("<!channel> OK, I shall now run an anonymous "
                "vote on whether *%s* should be invited to the channel. You should all get "
                "DMs with instructions." % (name,))])
            ask_users(data["channel"], name)
        else:
            outputs.append([data["channel"], 
                ("Hey, <@%s>, to ask me to run an anonymous vote on whether someone should "
                 "be invited to the channel, "
                 "say `@vote on Jane Smith`.") % (data["user"],)])



def setup(fn):
    global get_slack
    print "Anonymous vote bot starting up"
    get_slack = fn
