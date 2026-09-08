from repository import Repository
from telebot import TeleBot
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from prometheus_client import Counter, start_http_server
from logger import Logger
import os

class HammBotController:

    model: Repository
    reply_keyboard: ReplyKeyboardMarkup
    confirm_button: InlineKeyboardButton
    decline_button: InlineKeyboardButton
    inline_confirm_keyboard: InlineKeyboardMarkup
    
    # Prometheus metrics
    inflow_counter = Counter('bot_inflow_total', 'Total inflow transactions')
    outflow_counter = Counter('bot_outflow_total', 'Total outflow transactions')
    message_counter = Counter('bot_messages_total', 'Total messages received')
    callback_counter = Counter('bot_callbacks_total', 'Total callback queries received')
    
    def __init__(self, token: str):
        log_file = os.path.join(os.path.dirname(__file__), '..', 'logs', 'bot.log')
        Logger.configure(log_file=log_file)
        self.logger = Logger.get_logger(__name__)
        self.logger.info("Initializing bot")

        self.bot = TeleBot(token=token)
        self.confirm_button = InlineKeyboardButton(text="Confirm", callback_data="confirm")
        self.decline_button = InlineKeyboardButton(text="Decline", callback_data="decline")
        self.reply_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        self.inline_confirm_keyboard = InlineKeyboardMarkup()
        self.inline_confirm_keyboard.add(self.confirm_button, self.decline_button)
        self.reply_keyboard.add("Inflow", "Outflow")
        self.model = Repository()

        # Register handlers
        self._register_handlers()

        # Start Prometheus metrics server
        start_http_server(8000)
        self.logger.info("Prometheus metrics server started on port 8000")

        # Start log server
        log_port = Logger.start_log_server(log_file)
        self.logger.info(f"Log server started on port {log_port}")

    def _register_handlers(self):
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback_query(call):
            """
                Find out if the action was inflow or outflow before checking the confirmation.
            """
            self.callback_counter.inc()
            self.logger.info("Callback received", user_id=call.from_user.id, callback_data=call.data)

            try:
                # Answer callback immediately to prevent timeout
                self.bot.answer_callback_query(call.id, "Processing...")

                if call.data == "confirm":
                    value = ''.join(filter(str.isdigit, call.message.text))

                    # Remove keyboard immediately
                    self.bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

                    # Process database operation after answering
                    self.model.inflow(call.from_user.id, value)
                    self.inflow_counter.inc()
                    self.logger.info("Inflow confirmed", user_id=call.from_user.id, value=value)

                elif call.data == "decline":
                    self.bot.answer_callback_query(call.id, "Declined")
                    self.bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
                    self.logger.info("Transaction declined", user_id=call.from_user.id)

            except Exception as e:
                self.logger.error("Callback error", error=str(e), user_id=call.from_user.id)
                # Try to remove the keyboard even if answering failed
                try:
                    self.bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
                except:
                    pass
                # Try to send a message to the user if callback failed
                try:
                    self.bot.send_message(call.message.chat.id, "Transaction processed (callback expired)")
                except:
                    pass

        @self.bot.message_handler(commands=['start'])
        def send_welcome(message):
            self.message_counter.inc()
            self.logger.info("Start command received", user_id=message.from_user.id)
            self.bot.reply_to(message, "check the following keyboard!", reply_markup=self.reply_keyboard)

            if not self.model.user_exists(message.from_user.id):
                self.model.user_create_if_not_exists(message.from_user.id)
                self.logger.info("New user created", user_id=message.from_user.id)

        @self.bot.message_handler(func=lambda message: True)
        def echo_all(message):
            self.message_counter.inc()
            self.logger.info("Message received", user_id=message.from_user.id, message_text=message.text)
            match message.text:
                case "Inflow":
                    self.bot.reply_to(message, "How much money did you receive?")
                    self.bot.register_next_step_handler(message, self.handle_inflow)
                case "Outflow":
                    self.bot.reply_to(message, "How much money did you spend?")
                    self.bot.register_next_step_handler(message, self.handle_outflow)
                case _:
                    self.bot.reply_to(
                        message,
                        "Please select 'Inflow' or 'Outflow' from the keyboard first.",
                        reply_markup=self.reply_keyboard
                    )

    def handle_inflow(self, message):
        self.message_counter.inc()
        value = ''.join(filter(str.isdigit, message.text))
        self.logger.info("Inflow amount received", user_id=message.from_user.id, value=value)
        self.bot.reply_to(message, f'You received ${value}.', reply_markup=self.inline_confirm_keyboard)

    def handle_outflow(self, message):
        self.message_counter.inc()
        value = ''.join(filter(str.isdigit, message.text))
        self.logger.info("Outflow amount received", user_id=message.from_user.id, value=value)
        self.bot.reply_to(message, f'You spent ${value}.', reply_markup=self.inline_confirm_keyboard)
        self.model.outflow(message.from_user.id, value)
        self.outflow_counter.inc()

    def start(self):
        self.logger.info("Starting bot polling")
        self.bot.polling()
