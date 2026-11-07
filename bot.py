import logging
import requests
import datetime
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.request import HTTPXRequest

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbwffgUY4I3uNwANxx8Xy6Cpcl46Xhxj7LA2t2Uufevzin0wac3gsPlE8JIZ1rPWd9JwLA/exec"
TOKEN = "5555514033:AAHyFSg590H6axuO6K1tT-InZQNq7WRWQcw"

(
    LOGIN_PIN, MENU_ACTIVE,
    POS_PILIH_MENU, POS_PILIH_VARIAN, POS_INPUT_JUMLAH, POS_KONFIRMASI_KERANJANG,
    LAP_PILIH_RIDER, LAP_INPUT_TANGGAL
) = range(8)

PROXIES = {
    'http': 'http://proxy.server:3128',
    'https': 'http://proxy.server:3128'
} if os.path.exists('/etc/pythonanywhere/') else None

def get_users_from_sheet():
    try:
        res = requests.get(f"{WEB_APP_URL}?action=get_rider", proxies=PROXIES).json()
        users = {}
        for row in res[1:]:
            if len(row) >= 3 and str(row[0]).strip() != "":
                pin = str(row[0]).strip()
                nama = str(row[1]).strip()
                role = str(row[2]).strip().lower()
                users[pin] = {"nama": nama, "role": role}
        return users
    except Exception as e:
        print("Error fetch rider:", e)
        return {"1510": {"nama": "Dimas", "role": "superuser"}}

def get_menu_with_varian():
    try:
        res = requests.get(f"{WEB_APP_URL}?action=get_menu", proxies=PROXIES).json()
        menu_data = {}
        current_menu = ""
        for row in res[1:]:
            if not row or len(row) < 3:
                continue
            nama = str(row[0]).strip()
            varian = str(row[1]).strip()
            harga = row[2]
            if nama != "":
                current_menu = nama
            if current_menu and varian and str(harga).isdigit():
                if current_menu not in menu_data:
                    menu_data[current_menu] = {}
                menu_data[current_menu][varian] = int(harga)
        return menu_data
    except Exception as e:
        print("Error fetch menu:", e)
        return {}

def get_bahan_from_sheet():
    try:
        res = requests.get(f"{WEB_APP_URL}?action=get_bahan", proxies=PROXIES).json()
        bahan_list = []
        for row in res[1:]:
            if len(row) >= 3 and str(row[0]).strip() != "":
                bahan_list.append({
                    "nama": str(row[0]).strip(),
                    "stok": str(row[1]).strip(),
                    "satuan": str(row[2]).strip()
                })
        return bahan_list
    except Exception as e:
        print("Error fetch bahan:", e)
        return []

def get_penjualan_from_sheet():
    try:
        res = requests.get(f"{WEB_APP_URL}?action=get_penjualan", proxies=PROXIES).json()
        return res[1:]
    except Exception as e:
        print("Error fetch penjualan:", e)
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("☕ *ENDINGE ES KOPI BOT*\n\nSilakan masukkan PIN Login Anda:", parse_mode='Markdown')
    return LOGIN_PIN

async def check_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pin_input = update.message.text.strip()
    users_db = get_users_from_sheet()
    
    if pin_input in users_db:
        user_info = users_db[pin_input]
        context.user_data['user_info'] = user_info
        nama = user_info['nama']
        role = user_info['role']
        
        if role == 'superuser':
            buttons = [
                [InlineKeyboardButton("📊 Cek Laporan Penjualan", callback_data="super_laporan")],
                [InlineKeyboardButton("📦 Stok Bahan", callback_data="super_stok"), InlineKeyboardButton("💰 Total Penghasilan", callback_data="super_profit")],
                [InlineKeyboardButton("🚪 Keluar / Logout", callback_data="app_logout")]
            ]
            markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(
                f"👤 *Halo, Superuser {nama}!*\n\n"
                f"Status: `Active Superuser`\n"
                f"Sistem siap digunakan. Pilih menu di bawah ini:",
                reply_markup=markup,
                parse_mode='Markdown'
            )
            return MENU_ACTIVE
        else:
            buttons = [
                [InlineKeyboardButton("📝 Input Penjualan Baru", callback_data="rider_pos")],
                [InlineKeyboardButton("🚪 Keluar / Logout", callback_data="app_logout")]
            ]
            markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(
                f"🛵 *Halo, Rider {nama}!*\n\n"
                f"Status: `Active Rider`\n"
                f"Silakan tekan tombol di bawah untuk mencatat penjualan:",
                reply_markup=markup,
                parse_mode='Markdown'
            )
            return MENU_ACTIVE
    else:
        await update.message.reply_text("❌ PIN salah atau belum terdaftar di Google Sheets!")
        return LOGIN_PIN

async def cb_laporan_penjualan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    users_db = get_users_from_sheet()
    buttons = [[InlineKeyboardButton("Semua Rider", callback_data="lap_rider_ALL")]]
    
    for pin, u in users_db.items():
        if u['role'] == 'rider':
            buttons.append([InlineKeyboardButton(f"Rider: {u['nama']}", callback_data=f"lap_rider_{u['nama']}")])
            
    buttons.append([InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="back_to_main")])
    await query.edit_message_text("📊 *CEK LAPORAN PENJUALAN*\n\nPilih Rider yang ingin dicek laporannya:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
    return MENU_ACTIVE

async def callback_pilih_rider(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    rider_selected = query.data.split("lap_rider_")[1]
    context.user_data['filter_rider'] = rider_selected
    
    today_str = datetime.datetime.now().strftime("%d/%m/%Y")
    await query.edit_message_text(
        f"Rider terpilih: *{rider_selected}*\n\n"
        f"Ketikkan tanggal yang ingin dicek di kolom pesan (Format `DD/MM/YYYY`)\n"
        f"_(Contoh: `{today_str}` atau ketik `ALL` untuk semua tanggal)_:",
        parse_mode='Markdown'
    )
    return LAP_INPUT_TANGGAL

async def show_laporan_penjualan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tgl_input = update.message.text.strip()
    rider_selected = context.user_data.get('filter_rider', 'ALL')
    
    rows = get_penjualan_from_sheet()
    filtered_rows = []
    total_omset = 0
    
    for r in rows:
        if len(r) < 5:
            continue
        waktu = str(r[0])
        rider = str(r[1])
        menu = str(r[2])
        jumlah = int(r[3]) if str(r[3]).isdigit() else 0
        total_bayar = int(r[4]) if str(r[4]).isdigit() else 0
        
        if rider_selected != "ALL" and rider != rider_selected:
            continue
            
        if tgl_input.upper() != "ALL" and tgl_input not in waktu:
            continue
            
        filtered_rows.append(f"• {waktu.split(',')[0]} | {rider} | {menu} x{jumlah} = Rp {total_bayar:,}")
        total_omset += total_bayar

    text_res = f"📊 *HASIL LAPORAN PENJUALAN*\nFilter: Rider `{rider_selected}` | Tgl `{tgl_input}`\n------------------------------------\n"
    if not filtered_rows:
        text_res += "Tidak ada data transaksi yang cocok."
    else:
        text_res += "\n".join(filtered_rows[:15])
        if len(filtered_rows) > 15:
            text_res += f"\n_...dan {len(filtered_rows)-15} transaksi lainnya._"
        text_res += f"\n------------------------------------\n💰 *Total Omset Penjualan: Rp {total_omset:,}*"
        
    buttons = [[InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="back_to_main")]]
    await update.message.reply_text(text_res, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
    return MENU_ACTIVE

async def cb_stok_bahan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    bahan_list = get_bahan_from_sheet()
    text = "📦 *STOK BAHAN TERSISA (GOOGLE SHEETS)*\n------------------------------------\n"
    if not bahan_list:
        text += "Belum ada data di Tab 'Bahan' Google Sheets."
    else:
        for b in bahan_list:
            text += f"• *{b['nama']}*: {b['stok']} {b['satuan']}\n"
            
    buttons = [[InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="back_to_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
    return MENU_ACTIVE

async def cb_total_penghasilan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    rows = get_penjualan_from_sheet()
    total_omset = 0
    total_cup = 0
    
    for r in rows:
        if len(r) >= 5:
            total_bayar = int(r[4]) if str(r[4]).isdigit() else 0
            jumlah = int(r[3]) if str(r[3]).isdigit() else 0
            total_omset += total_bayar
            total_cup += jumlah

    hpp_per_cup = 3500
    total_hpp = total_cup * hpp_per_cup
    laba_bersih = total_omset - total_hpp
    
    text = (
        f"💰 *TOTAL PENGHASILAN & PROFIT*\n"
        f"------------------------------------\n"
        f"💵 Total Omset Penjualan: Rp {total_omset:,}\n"
        f"🥤 Total Minuman Terjual: {total_cup} Cup\n"
        f"📦 Est. Total HPP Bahan: Rp {total_hpp:,}\n"
        f"------------------------------------\n"
        f"🎯 *Laba Bersih Estimasi: Rp {laba_bersih:,}*"
    )
    buttons = [[InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="back_to_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
    return MENU_ACTIVE

async def cb_start_pos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['cart'] = []
        
    menu_db = get_menu_with_varian()
    context.user_data['menu_db'] = menu_db
    
    if not menu_db:
        await query.edit_message_text("❌ Gagal mengambil menu. Pastikan Tab 'Menu' di Google Sheets terisi.")
        return MENU_ACTIVE

    buttons = []
    for m_nama in menu_db.keys():
        buttons.append([InlineKeyboardButton(m_nama, callback_data=f"posmenu_{m_nama}")])
        
    buttons.append([InlineKeyboardButton("🔙 Batal Transaksi", callback_data="back_to_main")])
    await query.edit_message_text("📋 *PILIH MENU MINUMAN:*", reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
    return MENU_ACTIVE

async def callback_pos_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    menu_nama = query.data.split("posmenu_")[1]
    context.user_data['pos_menu'] = menu_nama
    menu_db = context.user_data.get('menu_db', {})
    
    varians = menu_db.get(menu_nama, {})
    buttons = []
    for var, harga in varians.items():
        buttons.append([InlineKeyboardButton(f"Varian {var} (Rp {harga:,})", callback_data=f"posvar_{var}")])
        
    buttons.append([InlineKeyboardButton("🔙 Batal", callback_data="back_to_main")])
    await query.edit_message_text(f"🥤 Menu: *{menu_nama}*\n\nPilih Varian Ukuran:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
    return MENU_ACTIVE

async def callback_pos_varian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    varian = query.data.split("posvar_")[1]
    context.user_data['pos_varian'] = varian
    menu_nama = context.user_data['pos_menu']
    
    await query.edit_message_text(
        f"Menu terpilih: *{menu_nama} {varian}*\n\n"
        f"Ketikkan *JUMLAH PESANAN* di kolom pesan (angka saja):",
        parse_mode='Markdown'
    )
    return POS_INPUT_JUMLAH

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jumlah_str = update.message.text.strip()
    if not jumlah_str.isdigit():
        await update.message.reply_text("❌ Masukkan angka jumlah yang valid:")
        return POS_INPUT_JUMLAH
    
    jumlah = int(jumlah_str)
    menu_nama = context.user_data['pos_menu']
    varian = context.user_data['pos_varian']
    
    menu_db = context.user_data.get('menu_db', {})
    harga_satuan = menu_db[menu_nama][varian]
    subtotal = harga_satuan * jumlah
    full_menu_name = f"{menu_nama} {varian}"
    
    if 'cart' not in context.user_data:
        context.user_data['cart'] = []
        
    context.user_data['cart'].append({
        "menu": full_menu_name,
        "jumlah": jumlah,
        "total_bayar": subtotal
    })
    
    cart_items = context.user_data['cart']
    text_cart = "🛒 *RINGKASAN STRUK PESANAN SAAT INI:*\n------------------------------------\n"
    grand_total = 0
    
    for idx, item in enumerate(cart_items, 1):
        text_cart += f"{idx}. *{item['menu']}* x{item['jumlah']} = Rp {item['total_bayar']:,}\n"
        grand_total += item['total_bayar']
        
    text_cart += f"------------------------------------\n💰 *Total Belanja: Rp {grand_total:,}*\n\nApakah ada pesanan menu lagi?"
    
    buttons = [
        [InlineKeyboardButton("➕ Ada Lagi (Tambah Menu)", callback_data="cart_add_more")],
        [InlineKeyboardButton("✅ Selesai & Simpan Struk", callback_data="cart_finish")]
    ]
    
    await update.message.reply_text(text_cart, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
    return MENU_ACTIVE

async def cb_cart_add_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    menu_db = get_menu_with_varian()
    context.user_data['menu_db'] = menu_db
    
    buttons = []
    for m_nama in menu_db.keys():
        buttons.append([InlineKeyboardButton(m_nama, callback_data=f"posmenu_{m_nama}")])
        
    buttons.append([InlineKeyboardButton("🔙 Batal", callback_data="back_to_main")])
    await query.edit_message_text("📋 *PILIH MENU TAMBAHAN:*", reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
    return MENU_ACTIVE

async def cb_cart_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cart_items = context.user_data.get('cart', [])
    if not cart_items:
        await query.edit_message_text("❌ Keranjang belanja kosong.")
        return MENU_ACTIVE
        
    rider_nama = context.user_data['user_info']['nama']
    grand_total = 0
    text_struk_final = f"✅ *TRANSAKSI BERHASIL DISIMPAN KE GOOGLE SHEETS!*\n"
    text_struk_final += f"• *Rider:* {rider_nama}\n------------------------------------\n"
    
    for item in cart_items:
        payload = {
            "action": "input_penjualan",
            "rider": rider_nama,
            "menu": item['menu'],
            "jumlah": item['jumlah'],
            "total_bayar": item['total_bayar']
        }
        try:
            requests.post(WEB_APP_URL, json=payload, proxies=PROXIES)
        except Exception as e:
            print("Error posting item to sheet:", e)
            
        text_struk_final += f"• {item['menu']} x{item['jumlah']} (Rp {item['total_bayar']:,})\n"
        grand_total += item['total_bayar']
        
    text_struk_final += f"------------------------------------\n💰 *TOTAL BAYAR STRUK: Rp {grand_total:,}*"
    
    context.user_data['cart'] = []
    
    buttons = [
        [InlineKeyboardButton("📝 Input Transaksi Baru", callback_data="rider_pos")],
        [InlineKeyboardButton("🚪 Keluar / Logout", callback_data="app_logout")]
    ]
    
    await query.edit_message_text(text_struk_final, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
    return MENU_ACTIVE

async def cb_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['cart'] = []
    
    user_info = context.user_data.get('user_info', {})
    nama = user_info.get('nama', 'User')
    role = user_info.get('role', 'rider')
    
    if role == 'superuser':
        buttons = [
            [InlineKeyboardButton("📊 Cek Laporan Penjualan", callback_data="super_laporan")],
            [InlineKeyboardButton("📦 Stok Bahan", callback_data="super_stok"), InlineKeyboardButton("💰 Total Penghasilan", callback_data="super_profit")],
            [InlineKeyboardButton("🚪 Keluar / Logout", callback_data="app_logout")]
        ]
        await query.edit_message_text(f"👤 *Halo, Superuser {nama}!*\nPilih menu di bawah ini:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
    else:
        buttons = [
            [InlineKeyboardButton("📝 Input Penjualan Baru", callback_data="rider_pos")],
            [InlineKeyboardButton("🚪 Keluar / Logout", callback_data="app_logout")]
        ]
        await query.edit_message_text(f"🛵 *Halo, Rider {nama}!*\nPilih menu di bawah ini:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode='Markdown')
        
    return MENU_ACTIVE

async def cb_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("👋 Anda telah keluar dari sistem bot.")
    return ConversationHandler.END

def main():
    # Mematikan job_queue agar pytz error hilang total
    builder = Application.builder().token(TOKEN).job_queue(None)
    
    if os.path.exists('/etc/pythonanywhere/'):
        req = HTTPXRequest(http_version="1.1", proxy="http://proxy.server:3128")
        builder.request(req).get_updates_request(req)

    app = builder.build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LOGIN_PIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_pin)],
            MENU_ACTIVE: [
                CallbackQueryHandler(cb_laporan_penjualan, pattern="^super_laporan$"),
                CallbackQueryHandler(cb_stok_bahan, pattern="^super_stok$"),
                CallbackQueryHandler(cb_total_penghasilan, pattern="^super_profit$"),
                CallbackQueryHandler(cb_start_pos, pattern="^rider_pos$"),
                CallbackQueryHandler(callback_pos_menu, pattern="^posmenu_"),
                CallbackQueryHandler(callback_pos_varian, pattern="^posvar_"),
                CallbackQueryHandler(cb_cart_add_more, pattern="^cart_add_more$"),
                CallbackQueryHandler(cb_cart_finish, pattern="^cart_finish$"),
                CallbackQueryHandler(cb_back_to_main, pattern="^back_to_main$"),
                CallbackQueryHandler(cb_logout, pattern="^app_logout$"),
                CallbackQueryHandler(callback_pilih_rider, pattern="^lap_rider_")
            ],
            POS_INPUT_JUMLAH: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_to_cart)],
            LAP_INPUT_TANGGAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_laporan_penjualan)],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    app.add_handler(conv_handler)
    print("Bot Keranjang Multi-Menu Berjalan...")
    app.run_polling()

if __name__ == '__main__':
    main()
