"""English strings."""

T = {
    # Start
    "start_welcome": (
        "🕶 <b>Anonex</b>\n\n"
        "Anonymous P2P marketplace.\n"
        "Your ID: <code>{ghost_id}</code>{rating_line}\n\n"
        "No registration. No names.\n"
        "Just you, the seller, and crypto.\n\n"
        "Use the menu below 👇"
    ),
    "start_rating": "\nYour rating: ⭐ {avg:.1f} ({count} reviews)",
    "help_text": (
        "📖 <b>How Anonex works</b>\n\n"
        "1. <b>🛒 Market</b> → pick an item → pay in USDT via CryptoBot\n"
        "2. <b>Escrow</b> → funds frozen until you confirm receipt\n"
        "3. Seller delivers the item inside the bot\n"
        "4. You confirm → funds go to seller\n"
        "5. No reply in 48h → auto-confirmed\n"
        "6. Problem? Open a dispute — admin reviews manually\n"
        "7. After the deal, leave a ⭐ review\n\n"
        "💰 Fee: 10% | 👥 Referrals: 50% of fee forever\n"
        "⏳ Withdrawal: 7 days after confirmation\n"
        "🕒 Listing lifetime: 30 days"
    ),
    "referral_info": (
        "👥 <b>Anonex Referral Program</b>\n\n"
        "50% of the platform fee from every deal of your invitees — forever.\n\n"
        "Your link:\n<code>{link}</code>\n\n"
        "Invited: <b>{count}</b>"
    ),
    "lang_changed": "✅ Language set to English.",

    # Menu buttons
    "btn_market": "🛒 Market",
    "btn_sell": "➕ Sell",
    "btn_purchases": "📦 My Purchases",
    "btn_listings": "📋 My Listings",
    "btn_wallet": "💼 Wallet",
    "btn_referral": "👥 Referral",
    "btn_language": "🌐 Language",

    # Listing creation
    "sell_start": (
        "📝 <b>New listing</b>\n\n"
        "<i>Active for 30 days.</i>\n\n"
        "Enter a title (3–100 characters):"
    ),
    "sell_title_short": "Too short. Minimum 3 characters.",
    "sell_title_long": "Too long. Maximum 100 characters.",
    "sell_title_text": "Please enter a text title.",
    "sell_desc_prompt": "Description (10–1000 characters):",
    "sell_desc_short": "Too short. Minimum 10 characters.",
    "sell_desc_long": "Too long. Maximum 1000 characters.",
    "sell_desc_text": "Please enter a text description.",
    "sell_price_prompt": "💵 Price in USDT (min 0.50):",
    "sell_price_min": "Minimum price is 0.50 USDT.",
    "sell_price_max": "Maximum price is 100,000 USDT.",
    "sell_price_invalid": "Invalid price. Example: 5.00",
    "sell_price_text": "Enter a number.",
    "sell_cat_prompt": "Choose a category:",
    "sell_cat_buttons": "Use the buttons above 👆",
    "sell_subcat_prompt": "{emoji} <b>{name}</b>\nChoose a subcategory:",
    "sell_file_prompt": (
        "Category: {label}\n\n"
        "📎 Attach a file (optional).\n"
        "Or type <b>no</b> to skip."
    ),
    "sell_file_hint": "Send a file or type <b>no</b> to skip.",
    "sell_session_broken": "Session corrupted. Please start over.",
    "sell_published": (
        "✅ Published! Active for 30 days.\n\n"
        "<b>{title}</b> — <b>{price} USDT</b>\n"
        "📂 {label}\n"
        "ID: <code>{id}</code>"
    ),
    "sell_suggest_cat": "💡 Enter the name of the category you want to add:",
    "sell_suggest_sent": "✅ Request sent. Admin will review it.",
    "sell_suggest_invalid": "2–100 characters.",

    # Market
    "market_choose_cat": "🛒 <b>Anonex Market</b>\nChoose a category:",
    "market_empty_cat": "No listings in this category yet.",
    "market_empty": "Market is empty. Be the first seller! ➕",
    "market_no_more": "No more listings.",
    "market_header": "🛒 <b>Anonex Market</b>",
    "market_no_reviews": "⭐ no reviews",
    "market_suggest_btn": "💡 Suggest a category",

    # Reviews
    "reviews_none": "⭐ <b>{ghost}</b>\n\nNo reviews yet.",
    "reviews_header": "⭐ <b>{ghost}</b>\nAverage: <b>{avg:.1f}</b> / 5  ({count})\n",
    "rate_prompt": (
        "⭐ <b>Rate deal #{order_id}</b>\n\n"
        "Leave a rating for the seller — it helps other buyers."
    ),
    "rate_text_prompt": (
        "Rating: {stars}\n\n"
        "Add a comment? (up to 500 chars)\n"
        "Or type /skip to leave only stars."
    ),
    "rate_saved": "✅ Review saved.\n\n{stars}",
    "rate_skipped": "Got it, review skipped.",
    "rate_already": "You already reviewed this deal.",
    "rate_invalid": "Invalid rating.",
    "rate_no_access": "No access.",
    "rate_wrong_status": "You can only review a completed deal.",
    "rate_failed": "Failed to save review.",
    "rate_seller_notif": "⭐ New review for deal #{order_id}: {stars}",

    # Orders
    "order_unavailable": "This listing is no longer available.",
    "order_self": "You can't buy from yourself.",
    "order_duplicate": "You already have an active order for this item.",
    "order_invoice_error": "Invoice creation failed. Try again later.",
    "order_created": (
        "🛒 <b>Order #{id}</b>\n\n"
        "Item: <b>{title}</b>\n"
        "Amount: <b>{amount} USDT</b>\n"
        "Platform fee: {fee} USDT (10%)\n\n"
        "Pay via CryptoBot, then tap «Check payment»."
    ),
    "order_already_processed": "Already processed.",
    "order_not_paid": "Payment not received yet.",
    "order_check_error": "Could not check. Try again later.",
    "order_paid_ok": (
        "✅ <b>Payment confirmed!</b>\n"
        "Order #{id} in escrow. Waiting for seller to deliver."
    ),
    "order_seller_notif": (
        "💰 <b>New paid deal #{id}</b>\n"
        "Amount: {amount} USDT → you get {net} USDT\n"
        "Deliver the item to the buyer:"
    ),
    "order_cancel_ok": "❌ Order #{id} cancelled.",
    "order_cancel_fail": "Can only cancel unpaid orders.",
    "order_no_access": "No access.",
    "order_not_found": "Order not found.",
    "purchases_empty": "You have no purchases yet.",
    "deliver_prompt": (
        "📤 <b>Order #{id}</b>\n"
        "Send the item / link / access code. It will be delivered anonymously."
    ),
    "deliver_status_changed": "Order #{id} status changed. Delivery not possible.",
    "deliver_already_changed": "Status already changed.",
    "deliver_ok": "✅ Delivered. Waiting for buyer confirmation (auto in 48h).",
    "deliver_buyer_notif": (
        "📦 <b>Seller delivered order #{id}.</b>\n"
        "Confirm receipt or open a dispute."
    ),
    "deliver_buyer_text": "📦 <b>Order #{id} delivered:</b>\n\n{note}",
    "confirm_ok": "✅ Order #{id} completed. Thank you!",
    "confirm_status": "Status already: {label}",
    "release_seller_notif": "🎉 <b>Deal #{id} completed!</b>\n+{net} USDT (withdrawal in 7 days)",
    "release_referral_notif": "💸 Referral reward: <b>+{amount} USDT</b> (deal #{id})",
    "dispute_prompt": "⚠️ <b>Dispute for order #{id}</b>\nDescribe the problem:",
    "dispute_wrong_status": "You can only open a dispute on an active order.",
    "dispute_opened": "⚠️ Dispute opened. Funds frozen until resolved.",
    "dispute_failed": "Could not open dispute (status changed).",
    "dispute_admin_notif": (
        "⚠️ <b>Dispute — Order #{id}</b>\n"
        "Buyer: <code>{ghost}</code>\n"
        "Reason: {reason}"
    ),
    "dispute_text_only": "Please describe the problem in text.",

    # Wallet
    "wallet_info": (
        "💼 <b>Wallet</b>\n\n"
        "Available: <b>{balance} USDT</b>\n"
        "Frozen: <b>{pending} USDT</b> ⏳\n"
        "Total earned: {earned} USDT\n\n"
        "<i>Frozen funds unlock 7 days after deal confirmation.</i>"
    ),
    "withdraw_min": "Min withdrawal: 1.00 USDT. You have: {balance}",
    "withdraw_prompt": "📤 Available: <b>{balance} USDT</b>\nEnter amount (min 1.00):",
    "withdraw_min_amount": "Minimum 1.00 USDT.",
    "withdraw_insufficient": "Insufficient funds. Available: {balance} USDT",
    "withdraw_invalid": "Invalid amount.",
    "withdraw_addr_prompt": (
        "Enter withdrawal address:\n\n"
        "• TRC20 USDT: <code>T...</code> (34 chars)\n"
        "• Telegram ID: 5–12 digits"
    ),
    "withdraw_addr_invalid": (
        "❌ Invalid address.\n\n"
        "Expected TRC20 (starts with T, 34 chars)\n"
        "or Telegram ID (5–12 digits)."
    ),
    "withdraw_session_expired": "Session expired. Start over.",
    "withdraw_balance_changed": "Balance changed. Start over.",
    "withdraw_created": (
        "✅ Withdrawal request <b>{amount} USDT</b> created.\n"
        "Address: <code>{addr}</code>\n\n"
        "Processing within 24 hours."
    ),
    "withdraw_admin_notif": (
        "💸 <b>Withdrawal #{id}</b>\n"
        "<code>{ghost}</code> | {amount} USDT\n"
        "Address: <code>{wallet}</code>"
    ),
    "tx_empty": "No transactions yet.",
    "tx_header": "📊 <b>Transactions</b>\n",
    "tx_types": {
        "escrow_in": "🔒 Escrow",
        "escrow_release": "📤 Release",
        "fee": "💸 Fee",
        "referral": "👥 Referral",
        "refund": "↩️ Refund",
        "withdrawal": "📤 Withdrawal",
    },

    # Admin
    "admin_panel": (
        "🔧 <b>Admin Panel</b>\n\n"
        "👤 Users: {users} | 📋 Listings: {listings}\n"
        "📦 Orders: {orders} | 💰 Volume: {volume} USDT\n"
        "💸 Fees: {fees} USDT\n"
        "⚠️ Disputes: {disputes} | 📤 Withdrawals: {withdrawals}"
    ),
    "admin_no_access": "No access.",
    "admin_no_disputes": "No open disputes 🎉",
    "admin_no_withdrawals": "No pending withdrawals.",
    "admin_no_transactions": "No transactions.",
    "admin_no_listings": "No active listings.",
    "admin_no_suggestions": "No pending suggestions.",
    "admin_dispute_resolved_buyer": "✅ Dispute #{id} — refund to buyer.",
    "admin_dispute_resolved_seller": "✅ Dispute #{id} — payout to seller (7d hold).",
    "admin_dispute_already": "Already resolved.",
    "admin_withdrawal_approved": "✅ Withdrawal #{id} — transferred.",
    "admin_withdrawal_rejected": "❌ Withdrawal #{id} rejected, funds returned.",
    "admin_withdrawal_already": "Already processed.",
    "admin_ban_ok": "✅ Banned: {ghost}",
    "admin_ban_fail": "❌ Not found: {ghost}",
    "admin_unban_ok": "✅ Unbanned: {ghost}",
    "admin_unban_fail": "❌ Not found: {ghost}",
    "admin_listing_deleted": "✅ Deleted.",
    "admin_listing_delete_fail": "Failed.",
    "admin_cat_created": "✅ Created: {emoji} {name} (ID {id})",
    "admin_cat_renamed": "✅ Renamed.",
    "admin_cat_rename_fail": "❌ Failed.",
    "admin_cat_disabled": "✅ Deactivated",
    "admin_cat_new_root_prompt": "Name of the new root category:",
    "admin_cat_new_emoji_prompt": "Emoji (1 char, e.g. 🎮):",
    "admin_cat_new_sub_prompt": "Subcategory name (emoji at start optional, e.g. «🎯 Valorant»):",
    "admin_cat_rename_prompt": "New name (emoji at start optional):",
    "admin_sug_where": "Where to add «{name}»?",
    "admin_sug_name_prompt": (
        "Suggestion: «{name}»\n\n"
        "Enter final name (emoji at start optional)\n"
        "or type <b>=</b> to accept as-is:"
    ),
    "admin_sug_approved": "✅ Category created: {emoji} {name} (ID {id})",
    "admin_sug_rejected": "Rejected.",
    "admin_sug_already": "Already processed.",
    "admin_sug_user_approved": "✅ Your suggestion «{name}» was approved!\nCategory {emoji} {cat_name} added.",
    "admin_sug_user_rejected": "❌ Your suggestion «{name}» was rejected.",
    "admin_buyer_notif": "↩️ Dispute #{id} resolved in your favour. +{amount} USDT",
    "admin_seller_notif_buyer_won": "⚠️ Dispute #{id} — refund to buyer.",
    "admin_seller_notif_seller_won": "✅ Dispute #{id} resolved in your favour. Funds on hold (7d).",
    "admin_buyer_notif_seller_won": "⚠️ Dispute #{id} — resolved in seller's favour.",
    "admin_withdrawal_user_ok": "✅ Withdrawal #{id}: {amount} USDT sent.",
    "admin_withdrawal_user_fail": "❌ Withdrawal #{id} failed. {amount} USDT returned.",
    "admin_withdrawal_user_rejected": "❌ Withdrawal #{id} rejected. {amount} USDT returned.",
    "admin_listing_seller_notif": "🛑 Your listing «{title}» was removed by admin.",

    # Scheduler
    "sched_auto_confirmed": "⏰ Order #{id} auto-confirmed (48h passed).",
    "sched_unlocked": "🔓 <b>Funds unlocked!</b>\nOrder #{id}: +{amount} USDT available for withdrawal.",
}
