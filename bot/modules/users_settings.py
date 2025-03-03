from functools import partial
from html import escape
from math import ceil
from os import mkdir, path, remove
from time import sleep, time

from PIL import Image
from telegram.ext import (CallbackQueryHandler, CommandHandler, Filters,
                          MessageHandler)

from bot import (DATABASE_URL, IS_PREMIUM_USER, MAX_SPLIT_SIZE, config_dict,
                 dispatcher, user_data)
from bot.helper.ext_utils.bot_utils import (get_readable_file_size,
                                            update_user_ldata)
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import (editMessage, sendMessage, sendFile,
                                                      sendPhoto)

handler_dict = {}

def get_user_settings(from_user):
    user_id = from_user.id
    name = from_user.full_name
    buttons = ButtonMaker()
    thumbpath = f"Thumbnails/{user_id}.jpg"
    user_dict = user_data.get(user_id, {})

    AD = config_dict['AS_DOCUMENT']
    if not user_dict and AD or user_dict.get('as_doc') or 'as_doc' not in user_dict and AD:
        ltype = "DOCUMENT"
        buttons.sbutton("Send As Media", f"userset {user_id} med")
    else:
        ltype = "MEDIA"
        buttons.sbutton("Send As Document", f"userset {user_id} doc")

    buttons.sbutton("Leech Splits", f"userset {user_id} lss")
    split_size = user_dict.get('split_size') or config_dict['LEECH_SPLIT_SIZE']
    split_size = get_readable_file_size(split_size)

    ES = config_dict['EQUAL_SPLITS']
    if not user_dict and ES or user_dict.get('equal_splits') or 'equal_splits' not in user_dict and ES:
        equal_splits = 'Enabled'
    else:
        equal_splits = 'Disabled'

    MG = config_dict['MEDIA_GROUP']
    if not user_dict and MG or user_dict.get('media_group') or 'media_group' not in user_dict and MG:
        media_group = 'Enabled'
    else:
        media_group = 'Disabled'

    buttons.sbutton("YT-DLP Quality", f"userset {user_id} ytq")
    YQ = config_dict['YT_DLP_QUALITY']
    if user_dict.get('yt_ql'):
        ytq = user_dict['yt_ql']
    elif not user_dict and YQ or 'yt_ql' not in user_dict and YQ:
        ytq = YQ
    else:
        ytq = 'None'

    buttons.sbutton("Thumbnail", f"userset {user_id} sthumb")
    thumbmsg = "Exists" if path.exists(thumbpath) else "Not Exists"

    LP = config_dict['LEECH_FILENAME_PREFIX']
    if user_dict.get('lprefix'):
        lprefix = user_dict['lprefix']
    elif not user_dict and LP or 'lprefix' not in user_dict and LP:
        lprefix = LP
    else:
        lprefix = 'None'
    buttons.sbutton("Leech Prefix", f"userset {user_id} lprefix")

    buttons.sbutton("Close", f"userset {user_id} close")
    text = f"<u>Settings for <a href='tg://user?id={user_id}'>{name}</a></u>\n"\
            f"Leech Type is <b>{ltype}</b>\n"\
            f"Custom Thumbnail <b>{thumbmsg}</b>\n"\
            f"Leech Split Size is <b>{split_size}</b>\n"\
            f"Equal Splits is <b>{equal_splits}</b>\n"\
            f"YT-DLP Quality is <b><code>{escape(ytq)}</code></b>\n" \
            f"Media Group is <b>{media_group}</b>\n"\
            f"Leech Prefix is <code>{escape(lprefix)}</code>"
    return text, buttons.build_menu(1)

def update_user_settings(message, from_user):
    msg, button = get_user_settings(from_user)
    editMessage(msg, message, button)

def user_settings(update, context):
    msg, button = get_user_settings(update.message.from_user)
    sendMessage(msg, context.bot, update.message, button)

def set_yt_quality(update, context, omsg):
    message = update.message
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value = message.text
    update_user_ldata(user_id, 'yt_ql', value)
    update.message.delete()
    update_user_settings(omsg, message.from_user)
    if DATABASE_URL:
        DbManger().update_user_data(user_id)

def set_perfix(update, context, omsg):
    message = update.message
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value = message.text
    update_user_ldata(user_id, 'lprefix', value)
    update.message.delete()
    update_user_settings(omsg, message.from_user)
    if DATABASE_URL:
        DbManger().update_user_data(user_id)

def set_thumb(update, context, omsg):
    message = update.message
    user_id = message.from_user.id
    handler_dict[user_id] = False
    path_ = "Thumbnails/"
    if not path.isdir(path_):
        mkdir(path_)
    photo_dir = message.photo[-1].get_file().download()
    des_dir = path.join(path_, f'{user_id}.jpg')
    Image.open(photo_dir).convert("RGB").save(des_dir, "JPEG")
    remove(photo_dir)
    update_user_ldata(user_id, 'thumb', des_dir)
    update.message.delete()
    update_user_settings(omsg, message.from_user)
    if DATABASE_URL:
        DbManger().update_thumb(user_id, des_dir)

def leech_split_size(update, context, omsg):
    message = update.message
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value = min(ceil(float(message.text) * 1024 ** 3), MAX_SPLIT_SIZE)
    update_user_ldata(user_id, 'split_size', value)
    update.message.delete()
    update_user_settings(omsg, message.from_user)
    if DATABASE_URL:
        DbManger().update_user_data(user_id)

def edit_user_settings(update, context):
    query = update.callback_query
    message = query.message
    user_id = query.from_user.id
    data = query.data
    data = data.split()
    thumb_path = f"Thumbnails/{user_id}.jpg"
    user_dict = user_data.get(user_id, {})
    if user_id != int(data[1]):
        query.answer(text="Not Yours!", show_alert=True)
    elif data[2] == "doc":
        update_user_ldata(user_id, 'as_doc', True)
        query.answer()
        update_user_settings(message, query.from_user)
        if DATABASE_URL:
            DbManger().update_user_data(user_id)
    elif data[2] == "med":
        update_user_ldata(user_id, 'as_doc', False)
        query.answer()
        update_user_settings(message, query.from_user)
        if DATABASE_URL:
            DbManger().update_user_data(user_id)
    elif data[2] == 'vthumb':
        query.answer()
        handler_dict[user_id] = False
        sendPhoto(f"Thumbnail for <a href='tg://user?id={user_id}'>{query.from_user.full_name}</a>",
                   context.bot, message, open(thumb_path, 'rb'))
        update_user_settings(message, query.from_user)
    elif data[2] == "dthumb":
        handler_dict[user_id] = False
        if path.lexists(thumb_path):
            query.answer()
            remove(thumb_path)
            update_user_ldata(user_id, 'thumb', '')
            update_user_settings(message, query.from_user)
            if DATABASE_URL:
                DbManger().update_thumb(user_id)
        else:
            query.answer(text="Old Settings", show_alert=True)
            update_user_settings(message, query.from_user)
    elif data[2] == "sthumb":
        query.answer()
        if handler_dict.get(user_id):
            handler_dict[user_id] = False
            sleep(0.5)
        handler_dict[user_id] = True
        buttons = ButtonMaker()
        if path.exists(thumb_path):
            buttons.sbutton("View Thumbnail", f"userset {user_id} vthumb")
            buttons.sbutton("Delete Thumbnail", f"userset {user_id} dthumb")
        buttons.sbutton("Back", f"userset {user_id} back")
        buttons.sbutton("Close", f"userset {user_id} close")
        editMessage('Send a photo to save it as custom thumbnail. Timeout: 60 sec', message, buttons.build_menu(1))
        partial_fnc = partial(set_thumb, omsg=message)
        photo_handler = MessageHandler(filters=Filters.photo & Filters.chat(message.chat.id) & Filters.user(user_id), 
                                       callback=partial_fnc)
        dispatcher.add_handler(photo_handler)
        start_time = time()
        while handler_dict[user_id]:
            if time() - start_time > 60:
                handler_dict[user_id] = False
                update_user_settings(message, query.from_user)
        dispatcher.remove_handler(photo_handler)
    elif data[2] == 'ytq':
        query.answer()
        if handler_dict.get(user_id):
            handler_dict[user_id] = False
            sleep(0.5)
        handler_dict[user_id] = True
        buttons = ButtonMaker()
        buttons.sbutton("Back", f"userset {user_id} back")
        if user_dict.get('yt_ql') or config_dict['YT_DLP_QUALITY']:
            buttons.sbutton("Remove YT-DLP Quality", f"userset {user_id} rytq", 'header')
        buttons.sbutton("Close", f"userset {user_id} close")
        rmsg = f'''
Send YT-DLP Qaulity. Timeout: 60 sec
Examples:
1. <code>{escape('bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]')}</code> this will give 1080p-mp4.
2. <code>{escape('bv*[height<=720][ext=webm]+ba/b[height<=720]')}</code> this will give 720p-webm.
Check all available qualities options <a href="https://github.com/yt-dlp/yt-dlp#filtering-formats">HERE</a>.
        '''
        editMessage(rmsg, message, buttons.build_menu(1))
        partial_fnc = partial(set_yt_quality, omsg=message)
        value_handler = MessageHandler(filters=Filters.text & Filters.chat(message.chat.id) & Filters.user(user_id),
                                       callback=partial_fnc)
        dispatcher.add_handler(value_handler)
        start_time = time()
        while handler_dict[user_id]:
            if time() - start_time > 60:
                handler_dict[user_id] = False
                update_user_settings(message, query.from_user)
        dispatcher.remove_handler(value_handler)
    elif data[2] == 'rytq':
        query.answer()
        handler_dict[user_id] = False
        update_user_ldata(user_id, 'yt_ql', '')
        update_user_settings(message, query.from_user)
        if DATABASE_URL:
            DbManger().update_user_data(user_id)
    elif data[2] == 'lprefix':
        query.answer()
        if handler_dict.get(user_id):
            handler_dict[user_id] = False
            sleep(0.5)
        handler_dict[user_id] = True
        buttons = ButtonMaker()
        buttons.sbutton("Back", f"userset {user_id} back")
        LP = config_dict['LEECH_FILENAME_PREFIX']
        if not user_dict and LP or user_dict.get('lprefix') or 'lprefix' not in user_dict and LP:
            buttons.sbutton("Remove Leech Prefix", f"userset {user_id} rlpre", 'header')
        buttons.sbutton("Close", f"userset {user_id} close")
        rmsg = f'''
Send Leech Prefix. Timeout: 60 sec
Examples:
1. <code>{escape('<b>@JMDKH_Team</b>')}</code> 
This will give output of:
<b>@JMDKH_Team</b>  <code>50MB.bin</code>.

2. <code>{escape('<code>@JMDKH_Team</code>')}</code> 
This will give output of:
<code>@JMDKH_Team</code> <code>50MB.bin</code>.

Check all available formatting options <a href="https://core.telegram.org/bots/api#formatting-options">HERE</a>.
        '''
        editMessage(rmsg, message, buttons.build_menu(1))
        partial_fnc = partial(set_perfix, omsg=message)
        value_handler = MessageHandler(filters=Filters.text & Filters.chat(message.chat.id) & Filters.user(user_id),
                                       callback=partial_fnc)
        dispatcher.add_handler(value_handler)
        start_time = time()
        while handler_dict[user_id]:
            if time() - start_time > 60:
                handler_dict[user_id] = False
                update_user_settings(message, query.from_user)
        dispatcher.remove_handler(value_handler)
    elif data[2] == 'rlpre':
        query.answer(text="Leech Prefix Removed!", show_alert=True)
        update_user_ldata(user_id, 'lprefix', '')
        update_user_settings(message, query.from_user)
        if DATABASE_URL:
            DbManger().update_user_data(user_id)
    elif data[2] == 'lss':
        query.answer()
        if handler_dict.get(user_id):
            handler_dict[user_id] = False
            sleep(0.5)
        handler_dict[user_id] = True
        buttons = ButtonMaker()
        if user_dict.get('split_size'):
            buttons.sbutton("Reset Split Size", f"userset {user_id} rlss")
        ES = config_dict['EQUAL_SPLITS']
        if not user_dict and ES or user_dict.get('equal_splits') or 'equal_splits' not in user_dict and ES:
            buttons.sbutton("Disable Equal Splits", f"userset {user_id} esplits")
        else:
            buttons.sbutton("Enable Equal Splits", f"userset {user_id} esplits")
        MG = config_dict['MEDIA_GROUP']
        if not user_dict and MG or user_dict.get('media_group') or 'media_group' not in user_dict and MG:
            buttons.sbutton("Disable Media Group", f"userset {user_id} mgroup")
        else:
            buttons.sbutton("Enable Media Group", f"userset {user_id} mgroup")
        buttons.sbutton("Back", f"userset {user_id} back")
        buttons.sbutton("Close", f"userset {user_id} close")
        __msg = "Send Leech split size don't add unit, the default unit is <b>GB</b>\n"
        __msg += f"\nExamples:\n1 for 1GB\n0.5 for 512mb\n\nIS_PREMIUM_USER: {IS_PREMIUM_USER}. Timeout: 60 sec"
        editMessage(__msg, message, buttons.build_menu(1))
        partial_fnc = partial(leech_split_size, omsg=message)
        size_handler = MessageHandler(filters=Filters.text & Filters.chat(message.chat.id) & Filters.user(user_id),
                                      callback=partial_fnc)
        dispatcher.add_handler(size_handler)
        start_time = time()
        while handler_dict[user_id]:
            if time() - start_time > 60:
                handler_dict[user_id] = False
                update_user_settings(message, query.from_user)
        dispatcher.remove_handler(size_handler)
    elif data[2] == 'rlss':
        query.answer()
        handler_dict[user_id] = False
        update_user_ldata(user_id, 'split_size', '')
        update_user_settings(message, query.from_user)
        if DATABASE_URL:
            DbManger().update_user_data(user_id)
    elif data[2] == 'esplits':
        query.answer()
        handler_dict[user_id] = False
        update_user_ldata(user_id, 'equal_splits', not bool(user_dict.get('equal_splits')))
        update_user_settings(message, query.from_user)
        if DATABASE_URL:
            DbManger().update_user_data(user_id)
    elif data[2] == 'mgroup':
        query.answer()
        handler_dict[user_id] = False
        update_user_ldata(user_id, 'media_group', not bool(user_dict.get('media_group')))
        update_user_settings(message, query.from_user)
        if DATABASE_URL:
            DbManger().update_user_data(user_id)
    elif data[2] == 'back':
        query.answer()
        handler_dict[user_id] = False
        update_user_settings(message, query.from_user)
    else:
        query.answer()
        handler_dict[user_id] = False
        query.message.delete()
        query.message.reply_to_message.delete()

def send_users_settings(update, context):
    msg = f'{len(user_data)} users save there setting'
    for user, data in user_data.items():
        msg += f'\n\n<code>{user}</code>:'
        for key, value in data.items():
            msg += f'\n<b>{key}</b>: <code>{escape(str(value))}</code>'
    if len(msg.encode()) > 4000:
        sendFile(context.bot, update.message, msg, 'users_settings.txt')
    else:
        sendMessage(msg, context.bot, update.message)

users_settings_handler = CommandHandler(BotCommands.UsersCommand, send_users_settings,
                                            filters=CustomFilters.owner_filter | CustomFilters.sudo_user)
user_set_handler = CommandHandler(BotCommands.UserSetCommand, user_settings,
                                filters=((~Filters.sender_chat.super_group | ~Filters.sender_chat.channel)
                                & (CustomFilters.authorized_chat | CustomFilters.authorized_user)))
but_set_handler = CallbackQueryHandler(edit_user_settings, pattern="userset")

dispatcher.add_handler(user_set_handler)
dispatcher.add_handler(but_set_handler)
dispatcher.add_handler(users_settings_handler)
