from re import split
from threading import Thread
from time import sleep

from requests import request
from telegram.ext import CallbackQueryHandler, CommandHandler

from bot import (CATEGORY_NAMES, DATABASE_URL, DOWNLOAD_DIR, IS_USER_SESSION,
                 LOGGER, config_dict, dispatcher, user_data)
from bot.helper.ext_utils.bot_utils import (check_user_tasks,
                                            get_readable_file_size, is_url)
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.ext_utils.jmdkh_utils import extract_link
from bot.helper.mirror_utils.download_utils.yt_dlp_download_helper import YoutubeDLHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import (anno_checker,
                                                      chat_restrict,
                                                      delete_links,
                                                      editMessage, forcesub,
                                                      isAdmin, message_filter,
                                                      sendDmMessage,
                                                      sendLogMessage,
                                                      sendMessage)
from bot.modules.listener import MirrorLeechListener

listener_dict = {}

def _ytdl(bot, message, isZip=False, isLeech=False, sameDir={}):
    if not isLeech and not config_dict['GDRIVE_ID']:
        sendMessage('GDRIVE_ID not Provided!', bot, message)
        return
    mssg = message.text
    msg_id = message.message_id
    qual = ''
    select = False
    multi = 0
    index = 1
    link = ''
    folder_name = ''
    c_index = 0
    raw_url = None
    args = mssg.split(maxsplit=3)
    if len(args) > 1:
        for x in args:
            x = x.strip()
            if x in ['|', 'pswd:', 'opt:']:
                break
            elif x == 's':
               select = True
               index += 1
            elif x.strip().isdigit():
                multi = int(x)
                mi = index
            elif x.startswith('m:'):
                marg = x.split('m:', 1)
                if len(marg) > 1:
                    folder_name = f"/{marg[-1]}"
                    if not sameDir:
                        sameDir = set()
                    sameDir.add(message.message_id)
        if multi == 0:
            args = mssg.split(maxsplit=index)
            if len(args) > index:
                link = args[index].strip()
                if link.startswith(("|", "pswd:", "opt:")):
                    link = ''
                else:
                    link = split(r"opt:|pswd:|\|", link)[0]
                    link = link.strip()

    def __run_multi():
        if multi <= 1:
            return
        sleep(4)
        nextmsg = type('nextmsg', (object, ), {'chat_id': message.chat_id,
                                               'message_id': message.reply_to_message.message_id + 1})
        ymsg = mssg.split(maxsplit=mi+1)
        ymsg[mi] = f"{multi - 1}"
        nextmsg = sendMessage(" ".join(ymsg), bot, nextmsg)
        if len(folder_name) > 0:
            sameDir.add(nextmsg.message_id)
        nextmsg.from_user.id = message.from_user.id
        sleep(4)
        Thread(target=_ytdl, args=(bot, nextmsg, isZip, isLeech, sameDir)).start()

    dl_path = f'{DOWNLOAD_DIR}{message.message_id}{folder_name}'

    name = mssg.split('|', maxsplit=1)
    if len(name) > 1:
        if 'opt:' in name[0] or 'pswd:' in name[0]:
            name = ''
        else:
            name = split('pswd:|opt:', name[1])[0].strip()
    else:
        name = ''

    pswd = mssg.split(' pswd: ')
    pswd = pswd[1].split(' opt: ')[0] if len(pswd) > 1 else None

    opt = mssg.split(' opt: ')
    opt = opt[1] if len(opt) > 1 else ''

    if message.from_user.username:
        tag = f"@{message.from_user.username}"
    else:
        tag = message.from_user.mention_html(message.from_user.first_name)
    reply_to = message.reply_to_message
    if reply_to:
        if len(link) == 0 and reply_to.text:
            link = reply_to.text.split(maxsplit=1)[0].strip()
        if reply_to.from_user.username:
            tag = f"@{reply_to.from_user.username}"
        else:
            tag = reply_to.from_user.mention_html(reply_to.from_user.first_name)
    if (not is_url(link) or (link.isdigit() and multi == 0)) or reply_to and not reply_to.text:
        help_msg = """
<b>Send link along with command line:</b>
<code>/{cmd}</code> s link |newname pswd: xx(zip) opt: x:y|x1:y1

<b>By replying to link:</b>
<code>/{cmd}</code> |newname pswd: xx(zip) opt: x:y|x1:y1

<b>Quality Buttons:</b>
Incase default quality added but you need to select quality for specific link or links with multi links feature.
<code>/cmd</code> s link
This perfix should be always before |newname, pswd: and opt:

<b>Options Example:</b> opt: playliststart:^10|matchtitle:S13|writesubtitles:true|live_from_start:true|postprocessor_args:{fmg}|wait_for_video:(5, 100)

<b>Multi links only by replying to first link:</b>
<code>/{cmd}</code> 10(number of links)
Number should be always before |newname, pswd: and opt:

<b>Multi links within same upload directory only by replying to first link:</b>
<code>/cmd</code> 10(number of links) m:folder_name
Number and m:folder_name should be always before |newname, pswd: and opt:

<b>Options Note:</b> Add `^` before integer, some values must be integer and some string.
Like playlist_items:10 works with string, so no need to add `^` before the number but playlistend works only with integer so you must add `^` before the number like example above.
You can add tuple and dict also. Use double quotes inside dict.

<b>NOTE:</b>
You can add perfix randomly before link those for select (s) and mutli links (number).
You can't add perfix randomly after link. They should be arranged like exmaple above, rename then pswd then opt. If you don't want to add pswd for example then it will be (|newname opt:), just don't change the arrangement.
You can always add video quality from yt-dlp api options.

Check all yt-dlp api options from this <a href='https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L178'>FILE</a>.
        """
        return sendMessage(help_msg.format_map({'cmd': BotCommands.YtdlCommand[0], 'fmg': '{"ffmpeg": ["-threads", "4"]}'}), bot, message)
    if message.from_user.id in [1087968824, 136817688]:
        message.from_user.id = anno_checker(message)
        if not message.from_user.id:
            return
    user_id = message.from_user.id
    if not isAdmin(message):
        if message_filter(bot, message, tag):
            __run_multi()
            return
        if DATABASE_URL and config_dict['STOP_DUPLICATE_TASKS']:
            raw_url = extract_link(link)
            exist = DbManger().check_download(raw_url)
            if exist:
                _msg = f'<b>Download is already added by {exist["tag"]}</b>\n\nCheck the download status in @{exist["botname"]}\n\n<b>Link</b>: <code>{exist["_id"]}</code>'
                delete_links(bot, message)
                sendMessage(_msg, bot, message)
                __run_multi()
                return
        if forcesub(bot, message, tag):
            return
        if (maxtask:= config_dict['USER_MAX_TASKS']) and check_user_tasks(message.from_user.id, maxtask):
            return sendMessage(f"Your tasks limit exceeded for {maxtask} tasks", bot, message)
        if isLeech and config_dict['DISABLE_LEECH']:
            delete_links(bot, message)
            return sendMessage('Locked!', bot, message)
    if (dmMode:=config_dict['DM_MODE']) and message.chat.type == message.chat.SUPERGROUP:
        if isLeech and IS_USER_SESSION and not config_dict['DUMP_CHAT']:
            return sendMessage('DM_MODE and User Session need DUMP_CHAT', bot, message)
        dmMessage = sendDmMessage(bot, message, dmMode, isLeech)
        if dmMessage == 'BotNotStarted':
            return
    else:
        dmMessage = None
    logMessage = sendLogMessage(bot, message)
    chat_restrict(message)
    listener = MirrorLeechListener(bot, message, isZip, isLeech=isLeech, pswd=pswd,
                                tag=tag, sameDir=sameDir, raw_url=raw_url, c_index=c_index,
                                dmMessage=dmMessage, logMessage=logMessage)
    listener.mode = 'Leech' if isLeech else f'Drive {CATEGORY_NAMES[c_index]}'
    if isZip:
        listener.mode += ' as Zip'
    if 'mdisk.me' in link:
        name, link = _mdisk(link, name)
    ydl = YoutubeDLHelper(listener)
    try:
        result = ydl.extractMetaData(link, name, opt, True)
    except Exception as e:
        delete_links(bot, message)
        msg = str(e).replace('<', ' ').replace('>', ' ')
        sendMessage(f"{tag} {msg}", bot, message)
        __run_multi()
        return
    if not select:
        YTQ = config_dict['YT_DLP_QUALITY']
        user_dict = user_data.get(user_id, {})
        if 'format:' in opt:
            opts = opt.split('|')
            for f in opts:
                if f.startswith('format:'):
                    qual = f.split('format:', 1)[1]
        elif user_dict.get('yt_ql'):
            qual = user_dict['yt_ql']
        elif not user_dict and YTQ or 'yt_ql' not in user_dict and YTQ:
            qual = YTQ
    if qual:
        playlist = 'entries' in result
        LOGGER.info(f"Downloading with YT-DLP: {link} added by : {user_id}")
        Thread(target=ydl.add_download, args=(link, dl_path, name, qual, playlist, opt)).start()
    else:
        buttons = ButtonMaker()
        best_video = "bv*+ba/b"
        best_audio = "ba/b"
        formats_dict = {}
        if 'entries' in result:
            for i in ['144', '240', '360', '480', '720', '1080', '1440', '2160']:
                video_format = f"bv*[height<=?{i}][ext=mp4]+ba[ext=m4a]/b[height<=?{i}]"
                b_data = f"{i}|mp4"
                formats_dict[b_data] = video_format
                buttons.sbutton(f"{i}-mp4", f"qu {msg_id} {b_data} t")
                video_format = f"bv*[height<=?{i}][ext=webm]+ba/b[height<=?{i}]"
                b_data = f"{i}|webm"
                formats_dict[b_data] = video_format
                buttons.sbutton(f"{i}-webm", f"qu {msg_id} {b_data} t")
            buttons.sbutton("MP3", f"qu {msg_id} mp3 t")
            buttons.sbutton("Best Videos", f"qu {msg_id} {best_video} t")
            buttons.sbutton("Best Audios", f"qu {msg_id} {best_audio} t")
            buttons.sbutton("Cancel", f"qu {msg_id} cancel")
            YTBUTTONS = buttons.build_menu(3)
            bmsg = sendMessage('Choose Playlist Videos Quality:', bot, message, YTBUTTONS)
        else:
            formats = result.get('formats')
            is_m4a = False
            if formats is not None:
                for frmt in formats:
                    if frmt.get('tbr'):

                        format_id = frmt['format_id']

                        if frmt.get('filesize'):
                            size = frmt['filesize']
                        elif frmt.get('filesize_approx'):
                            size = frmt['filesize_approx']
                        else:
                            size = 0

                        if frmt.get('video_ext') == 'none' and frmt.get('acodec') != 'none':
                            if frmt.get('audio_ext') == 'm4a':
                                is_m4a = True
                            b_name = f"{frmt['acodec']}-{frmt['ext']}"
                            v_format = f"ba[format_id={format_id}]"
                        elif frmt.get('height'):
                            height = frmt['height']
                            ext = frmt['ext']
                            fps = frmt['fps'] if frmt.get('fps') else ''
                            b_name = f"{height}p{fps}-{ext}"
                            if ext == 'mp4':
                                ba_ext = '[ext=m4a]' if is_m4a else ''
                                v_format = f"bv*[format_id={format_id}]+ba{ba_ext}/b[height=?{height}]"
                            else:
                                v_format = f"bv*[format_id={format_id}]+ba/b[height=?{height}]"
                        else:
                            continue

                        if b_name in formats_dict:
                            formats_dict[b_name][str(frmt['tbr'])] = [size, v_format]
                        else:
                            subformat = {str(frmt['tbr']): [size, v_format]}
                            formats_dict[b_name] = subformat

                for b_name, d_dict in formats_dict.items():
                    if len(d_dict) == 1:
                        tbr, v_list = list(d_dict.items())[0]
                        buttonName = f"{b_name} ({get_readable_file_size(v_list[0])})"
                        buttons.sbutton(buttonName, f"qu {msg_id} {b_name}|{tbr}")
                    else:
                        buttons.sbutton(b_name, f"qu {msg_id} dict {b_name}")
            buttons.sbutton("MP3", f"qu {msg_id} mp3")
            buttons.sbutton("Best Video", f"qu {msg_id} {best_video}")
            buttons.sbutton("Best Audio", f"qu {msg_id} {best_audio}")
            buttons.sbutton("Cancel", f"qu {msg_id} cancel")
            YTBUTTONS = buttons.build_menu(2)
            bmsg = sendMessage('Choose Video quality\n\n<i>This Will Cancel Automatically in <u>2 Minutes</u></i>', bot, message, YTBUTTONS)
        listener_dict[msg_id] = [listener, user_id, link, name, YTBUTTONS, opt, formats_dict, dl_path]
        Thread(target=_auto_cancel, args=(bmsg, msg_id)).start()
    __run_multi()

def _qual_subbuttons(task_id, b_name, msg):
    buttons = ButtonMaker()
    task_info = listener_dict[task_id]
    formats_dict = task_info[6]
    for tbr, d_data in formats_dict[b_name].items():
        buttonName = f"{tbr}K ({get_readable_file_size(d_data[0])})"
        buttons.sbutton(buttonName, f"qu {task_id} {b_name}|{tbr}")
    buttons.sbutton("Back", f"qu {task_id} back")
    buttons.sbutton("Cancel", f"qu {task_id} cancel")
    SUBBUTTONS = buttons.build_menu(2)
    editMessage(f"Choose Bit rate for <b>{b_name}</b>:", msg, SUBBUTTONS)

def _mp3_subbuttons(task_id, msg, playlist=False):
    buttons = ButtonMaker()
    for q in [64, 128, 320]:
        if playlist:
            i = 's'
            audio_format = f"ba/b-{q} t"
        else:
            i = ''
            audio_format = f"ba/b-{q}"
        buttons.sbutton(f"{q}K-mp3", f"qu {task_id} {audio_format}")
    buttons.sbutton("Back", f"qu {task_id} back")
    buttons.sbutton("Cancel", f"qu {task_id} cancel")
    SUBBUTTONS = buttons.build_menu(2)
    editMessage(f"Choose Audio{i} Bitrate:", msg, SUBBUTTONS)

def select_format(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    msg = query.message
    data = data.split(" ")
    task_id = int(data[1])
    if task_id not in listener_dict:
        return editMessage("This is an old task", msg)
    task_info = listener_dict[task_id]
    uid = task_info[1]
    if user_id != uid and not CustomFilters.owner_query(user_id):
        return query.answer(text="This task is not for you!", show_alert=True)
    elif data[2] == "dict":
        query.answer()
        b_name = data[3]
        _qual_subbuttons(task_id, b_name, msg)
        return
    elif data[2] == "back":
        query.answer()
        return editMessage('Choose Video Quality:', msg, task_info[4])
    elif data[2] == "mp3":
        query.answer()
        playlist = len(data) == 4
        _mp3_subbuttons(task_id, msg, playlist)
        return
    elif data[2] == "cancel":
        query.answer()
        editMessage('Task has been cancelled.', msg)
    else:
        query.answer()
        listener = task_info[0]
        link = task_info[2]
        name = task_info[3]
        opt = task_info[5]
        qual = data[2]
        dl_path = task_info[7]
        if len(data) == 4:
            playlist = True
            if '|' in qual:
                qual = task_info[6][qual]
        else:
            playlist = False
            if '|' in qual:
                b_name, tbr = qual.split('|')
                qual = task_info[6][b_name][tbr][1]
        ydl = YoutubeDLHelper(listener)
        LOGGER.info(f"Downloading with YT-DLP: {link} added by : {user_id}")
        Thread(target=ydl.add_download, args=(link, dl_path, name, qual, playlist, opt)).start()
        query.message.delete()
    del listener_dict[task_id]

def _mdisk(link, name):
    key = link.split('/')[-1]
    resp = request('GET', f'https://diskuploader.entertainvideo.com/v1/file/cdnurl?param={key}', headers={
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://mdisk.me/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36'
    })
    if resp.ok:
        resp = resp.json()
        link = resp['source']
        if not name:
            name = resp['filename']
    return name, link

def _auto_cancel(msg, task_id):
    sleep(120)
    if task_id not in listener_dict:
        return
    del listener_dict[task_id]
    editMessage('Timed out! Task has been cancelled.', msg)


def ytdl(update, context):
    _ytdl(context.bot, update.message)

def ytdlZip(update, context):
    _ytdl(context.bot, update.message, True)

def ytdlleech(update, context):
    _ytdl(context.bot, update.message, isLeech=True)

def ytdlZipleech(update, context):
    _ytdl(context.bot, update.message, True, True)


ytdl_handler = CommandHandler(BotCommands.YtdlCommand, ytdl,
                              filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
ytdl_zip_handler = CommandHandler(BotCommands.YtdlZipCommand, ytdlZip,
                              filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
ytdl_leech_handler = CommandHandler(BotCommands.YtdlLeechCommand, ytdlleech,
                              filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
ytdl_zip_leech_handler = CommandHandler(BotCommands.YtdlZipLeechCommand, ytdlZipleech,
                              filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
quality_handler = CallbackQueryHandler(select_format, pattern="qu")
dispatcher.add_handler(ytdl_handler)
dispatcher.add_handler(ytdl_zip_handler)
dispatcher.add_handler(ytdl_leech_handler)
dispatcher.add_handler(ytdl_zip_leech_handler)
dispatcher.add_handler(quality_handler)