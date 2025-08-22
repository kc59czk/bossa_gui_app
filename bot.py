import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import socket
import struct
import winreg
import xml.etree.ElementTree as ET
import time
from datetime import datetime
from enum import Enum
import re

class BotState(Enum):
    STOPPED = 0
    IDLE = 1
    WAITING_FOR_BUY_FILL = 2
    IN_POSITION = 3
    WAITING_FOR_SELL_FILL = 4
    PANIC_SELLING = 5

class BossaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BossaAPI Klient dla PL0GF0031252")
        self.root.geometry("950x900")

        self.client = None
        self.queue = queue.Queue()
        self.TARGET_ISIN = "PL0GF0031252"
        self.orders = {}

        self.STATUS_MAP = {'0': 'Nowe', '1': 'Częściowo wyk.', '2': 'Wykonane', '4': 'Anulowane', '5': 'Zastąpione', '6': 'Oczekuje na anul.', '8': 'Odrzucone', 'E': 'Oczekuje na mod.'}
        self.SIDE_MAP = {'1': 'Kupno', '2': 'Sprzedaż'}

        self.create_widgets()
        self.process_queue()

    def create_widgets(self):
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='x', pady=(0, 5))

        self.tab_login = tk.Frame(self.notebook, padx=10, pady=10)
        self.notebook.add(self.tab_login, text="Połączenie i Filtr")

        self.tab_orders = tk.Frame(self.notebook, padx=10, pady=10)
        self.notebook.add(self.tab_orders, text="Zlecenia")

        self.tab_monitor = tk.Frame(self.notebook, padx=10, pady=10)
        self.notebook.add(self.tab_monitor, text="Monitor Zleceń")

        self.tab_bot = tk.Frame(self.notebook, padx=10, pady=10)
        self.notebook.add(self.tab_bot, text="Scalping Bot")

        # --- Nowa sekcja: Kafelki informacyjne ---
        tile_frame = tk.Frame(self.tab_bot, pady=10)
        tile_frame.pack(fill='x')

        def create_tile(parent, title):
            frame = tk.Frame(parent, relief='sunken', borderwidth=2)
            frame.pack(side='left', fill='x', expand=True, padx=5)
            title_label = tk.Label(frame, text=title, font=('Helvetica', 10, 'bold'))
            title_label.pack(pady=(5,0))
            value_label = tk.Label(frame, text="---", font=('Helvetica', 18, 'bold'), fg='blue')
            value_label.pack(pady=(0,5), padx=10)
            return value_label

        self.bid_label = create_tile(tile_frame, "BID")
        self.ask_label = create_tile(tile_frame, "ASK")
        self.last_label = create_tile(tile_frame, "LAST")
        self.be_label = create_tile(tile_frame, "BREAK-EVEN")
        self.pos_label = create_tile(tile_frame, "OTWARTE POZYCJE")

        bot_params_frame = tk.Frame(self.tab_bot, relief='groove', borderwidth=2, padx=5, pady=5)
        bot_params_frame.pack(fill='x')
        tk.Label(bot_params_frame, text="Parametry Bota:", font=('Helvetica', 10, 'bold')).pack(side='left', padx=(0,10))
        
        tk.Label(bot_params_frame, text="Zysk/transakcja:").pack(side='left')
        self.profit_entry = tk.Entry(bot_params_frame, width=5)
        self.profit_entry.pack(side='left', padx=(0,10))
        self.profit_entry.insert(0, "2")

        tk.Label(bot_params_frame, text="Stop-Loss:").pack(side='left')
        self.stoploss_entry = tk.Entry(bot_params_frame, width=5)
        self.stoploss_entry.pack(side='left', padx=(0,10))
        self.stoploss_entry.insert(0, "5")

        tk.Label(bot_params_frame, text="Cel dzienny:").pack(side='left')
        self.daily_goal_entry = tk.Entry(bot_params_frame, width=5)
        self.daily_goal_entry.pack(side='left', padx=(0,10))
        self.daily_goal_entry.insert(0, "20")

        self.start_bot_button = tk.Button(self.tab_bot, text="Start Bot", command=self.start_bot, state='disabled', bg='lightgreen')
        self.start_bot_button.pack(pady=5)
        self.stop_bot_button = tk.Button(self.tab_bot, text="Stop Bot", command=self.stop_bot, state='disabled', bg='salmon')
        self.stop_bot_button.pack(pady=5)

        tk.Label(self.tab_bot, text="Log Bota:").pack(anchor='w', pady=(10,0))
        self.bot_log = scrolledtext.ScrolledText(self.tab_bot, height=10, state='disabled')
        self.bot_log.pack(fill='both', expand=True)

        # ... (reszta create_widgets bez zmian)
        login_frame = tk.Frame(self.tab_login)
        login_frame.pack(fill='x', pady=(0, 10))
        tk.Label(login_frame, text="Użytkownik:").pack(side='left', padx=(0, 5))
        self.username_entry = tk.Entry(login_frame, width=20)
        self.username_entry.pack(side='left', padx=5)
        tk.Label(login_frame, text="Hasło:").pack(side='left', padx=5)
        self.password_entry = tk.Entry(login_frame, show="*", width=20)
        self.password_entry.pack(side='left', padx=5)
        self.username_entry.insert(0, "TWOJA_NAZWA_UŻYTKOWNIKA")
        self.password_entry.insert(0, "TWOJE_HASŁO")
        self.login_button = tk.Button(login_frame, text="Połącz i zaloguj", command=self.start_login_thread)
        self.login_button.pack(side='left', padx=10)
        self.disconnect_button = tk.Button(login_frame, text="Rozłącz", command=self.disconnect, state='disabled')
        self.disconnect_button.pack(side='left', padx=10)

        filter_frame = tk.Frame(self.tab_login, relief='groove', borderwidth=2, padx=5, pady=5)
        filter_frame.pack(fill='x', pady=5)
        tk.Label(filter_frame, text=f"Filtr notowań dla {self.TARGET_ISIN}:", font=('Helvetica', 10, 'bold')).pack(side='left', padx=(0, 10))
        self.add_filter_button = tk.Button(filter_frame, text=f"Dodaj {self.TARGET_ISIN} do filtra", command=self.add_to_filter, state='disabled')
        self.add_filter_button.pack(side='left', padx=5)
        self.clear_filter_button = tk.Button(filter_frame, text="Wyczyść filtr", command=self.clear_filter, state='disabled')
        self.clear_filter_button.pack(side='left', padx=5)

        order_frame = tk.Frame(self.tab_orders, relief='groove', borderwidth=2, padx=5, pady=5)
        order_frame.pack(fill='x', pady=5)
        tk.Label(order_frame, text=f"Nowe zlecenie (Limit, Dzień) dla {self.TARGET_ISIN}:", font=('Helvetica', 10, 'bold')).pack(anchor='w')
        controls_frame = tk.Frame(order_frame)
        controls_frame.pack(fill='x', pady=5)
        tk.Label(controls_frame, text="Rachunek:").pack(side='left', padx=(5, 5))
        self.account_entry = tk.Entry(controls_frame, width=15)
        self.account_entry.pack(side='left', padx=5)
        tk.Label(controls_frame, text="Kierunek:").pack(side='left', padx=(10, 5))
        self.direction_combo = ttk.Combobox(controls_frame, values=["Kupno", "Sprzedaż"], width=8)
        self.direction_combo.pack(side='left', padx=5)
        self.direction_combo.set("Kupno")
        tk.Label(controls_frame, text="Ilość:").pack(side='left', padx=(10, 5))
        self.quantity_entry = tk.Entry(controls_frame, width=8)
        self.quantity_entry.pack(side='left', padx=5)
        self.quantity_entry.insert(0, "1")
        tk.Label(controls_frame, text="Cena (Limit):").pack(side='left', padx=(10, 5))
        self.price_entry = tk.Entry(controls_frame, width=10)
        self.price_entry.pack(side='left', padx=5)
        self.send_order_button = tk.Button(controls_frame, text="Złóż zlecenie", command=self.send_order, state='disabled')
        self.send_order_button.pack(side='left', padx=10)

        cols = ('id_dm', 'id_klienta', 'status', 'symbol', 'k_s', 'ilosc', 'pozostalo', 'wykonano', 'limit', 'cena_ost', 'czas')
        self.order_tree = ttk.Treeview(self.tab_monitor, columns=cols, show='headings', height=10)
        col_map = {'id_dm': ('ID (DM)', 100), 'id_klienta': ('ID (Klient)', 80), 'status': ('Status', 120), 'symbol': ('Symbol', 80), 'k_s': ('K/S', 60), 'ilosc': ('Ilość', 60), 'pozostalo': ('Pozostało', 70), 'wykonano': ('Wykonano', 70), 'limit': ('Limit', 70), 'cena_ost': ('Cena ost.', 70), 'czas': ('Czas', 140)}
        for col, (text, width) in col_map.items():
            self.order_tree.heading(col, text=text)
            self.order_tree.column(col, width=width, anchor='center')
        vsb = ttk.Scrollbar(self.tab_monitor, orient="vertical", command=self.order_tree.yview)
        hsb = ttk.Scrollbar(self.tab_monitor, orient="horizontal", command=self.order_tree.xview)
        self.order_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        self.order_tree.pack(fill='both', expand=True)

        paned_window = tk.PanedWindow(main_frame, orient='vertical', sashrelief='raised')
        paned_window.pack(fill='both', expand=True, pady=5)
        top_panel = tk.Frame(paned_window)
        tk.Label(top_panel, text="Log statusu:").pack(anchor='w')
        self.status_log = scrolledtext.ScrolledText(top_panel, height=8, state='disabled')
        self.status_log.pack(fill='x', expand=True, pady=(0, 5))
        tk.Label(top_panel, text="Surowe komunikaty (kanał asynchroniczny):").pack(anchor='w')
        self.async_messages = scrolledtext.ScrolledText(top_panel, height=12, state='disabled', bg='lightgrey')
        self.async_messages.pack(fill='both', expand=True)
        paned_window.add(top_panel)
        bottom_panel = tk.Frame(paned_window)
        tk.Label(bottom_panel, text="Dane portfela:").pack(anchor='w')
        self.portfolio_display = scrolledtext.ScrolledText(bottom_panel, height=10, state='disabled')
        self.portfolio_display.pack(fill='both', expand=True)
        paned_window.add(bottom_panel)

    def process_queue(self):
        try:
            message_type, data = self.queue.get_nowait()
            
            if message_type == "MARKET_DATA_UPDATE":
                if data.get('isin') == self.TARGET_ISIN:
                    self.bid_label.config(text=f"{data.get('bid', '---'):.2f}")
                    self.ask_label.config(text=f"{data.get('ask', '---'):.2f}")
                    self.last_label.config(text=f"{data.get('last_price', '---'):.2f}")
                    
                    if self.root.focus_get() != self.price_entry:
                        self.price_entry.delete(0, tk.END)
                        self.price_entry.insert(0, f"{data.get('last_price', ''):.2f}")

            elif message_type == "BOT_STATE_UPDATE":
                self.pos_label.config(text=str(data.get('open_positions', '---')))
                entry_price = data.get('entry_price')
                if entry_price:
                    # Prowizja 1 pkt w każdą stronę
                    be_price = entry_price + 2 * 1
                    self.be_label.config(text=f"{be_price:.2f}")
                else:
                    self.be_label.config(text="---")

            # ... (pozostałe warunki bez zmian)
            elif message_type == "BOT_LOG":
                self.log_message(self.bot_log, data)
            elif message_type == "BOT_STOPPED":
                self.log_message(self.bot_log, "Bot zatrzymany.")
                self.start_bot_button.config(state='normal')
                self.stop_bot_button.config(state='disabled')
            elif message_type == "EXEC_REPORT":
                self.update_order_monitor(data)
            elif message_type == "LOG":
                self.log_message(self.status_log, data)
            elif message_type == "LOGIN_SUCCESS":
                self.log_message(self.status_log, f"Logowanie udane! Dodaj {self.TARGET_ISIN} do filtra, aby otrzymywać ceny.")
                self.disconnect_button.config(state='normal')
                self.add_filter_button.config(state='normal')
                self.clear_filter_button.config(state='normal')
                self.send_order_button.config(state='normal')
                self.start_bot_button.config(state='normal')
            elif message_type == "ASYNC_MSG":
                self.log_message(self.async_messages, data.strip())
            elif message_type == "PORTFOLIO":
                self.log_message(self.status_log, "Otrzymano dane portfela.")
                self.display_portfolio(data)
                if data and not self.account_entry.get():
                    first_account = next(iter(data))
                    self.account_entry.insert(0, first_account)
            elif message_type == "DISCONNECTED":
                self.log_message(self.status_log, "Rozłączono.")
                self.login_button.config(state='normal')
                self.disconnect_button.config(state='disabled')
                self.add_filter_button.config(state='disabled')
                self.clear_filter_button.config(state='disabled')
                self.send_order_button.config(state='disabled')
                self.start_bot_button.config(state='disabled')
                self.stop_bot_button.config(state='disabled')
                self.client = None
                self.orders = {}
                for i in self.order_tree.get_children(): self.order_tree.delete(i)
            elif message_type == "LOGIN_FAIL":
                self.log_message(self.status_log, f"Logowanie nie powiodło się: {data}")
                self.login_button.config(state='normal')
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)
    
    # Pozostałe metody bez zmian
    def start_bot(self):
        if not self.client:
            self.log_message(self.bot_log, "Błąd: Klient nie jest połączony.")
            return
        
        try:
            params = { 'account': self.account_entry.get(), 'profit_points': int(self.profit_entry.get()), 'stop_loss_points': int(self.stoploss_entry.get()), 'daily_goal': int(self.daily_goal_entry.get()), 'commission': 1 }
            if not params['account']:
                self.log_message(self.bot_log, "Błąd: Numer rachunku jest wymagany.")
                return
        except ValueError:
            self.log_message(self.bot_log, "Błąd: Parametry bota muszą być liczbami całkowitymi.")
            return

        self.start_bot_button.config(state='disabled')
        self.stop_bot_button.config(state='normal')
        self.log_message(self.bot_log, "Bot startuje...")
        threading.Thread(target=self.client.start_bot, args=(params,), daemon=True).start()

    def stop_bot(self):
        if self.client:
            self.log_message(self.bot_log, "Zatrzymywanie bota...")
            self.client.stop_bot()
            self.start_bot_button.config(state='normal')
            self.stop_bot_button.config(state='disabled')

    def update_order_monitor(self, data):
        order_id = data.get('id_dm')
        if not order_id: return
        data['status'] = self.STATUS_MAP.get(data['status'], data['status'])
        data['k_s'] = self.SIDE_MAP.get(data['k_s'], data['k_s'])
        values = [data.get(col, '') for col in ('id_dm', 'id_klienta', 'status', 'symbol', 'k_s', 'ilosc', 'pozostalo', 'wykonano', 'limit', 'cena_ost', 'czas')]
        if order_id in self.orders:
            item_id = self.orders[order_id]
            self.order_tree.item(item_id, values=values)
        else:
            item_id = self.order_tree.insert('', 'end', values=values)
            self.orders[order_id] = item_id

    def send_order(self):
        account = self.account_entry.get()
        direction = self.direction_combo.get()
        quantity_str = self.quantity_entry.get()
        price_str = self.price_entry.get()
        if not all([account, direction, quantity_str, price_str]):
            self.log_message(self.status_log, "BŁĄD: Wszystkie pola zlecenia muszą być wypełnione.")
            return
        try:
            quantity = int(quantity_str)
            if quantity <= 0: raise ValueError
        except ValueError:
            self.log_message(self.status_log, "BŁĄD: Ilość musi być dodatnią liczbą całkowitą.")
            return
        try:
            price = float(price_str)
            if price <= 0: raise ValueError
        except ValueError:
            self.log_message(self.status_log, "BŁĄD: Cena musi być dodatnią liczbą.")
            return
        if self.client:
            self.log_message(self.status_log, f"Przygotowywanie zlecenia {direction} {quantity} szt. {self.TARGET_ISIN} z limitem {price}...")
            params = (account, direction, quantity, price)
            threading.Thread(target=self.client.send_limit_order, args=params, daemon=True).start()

    def log_message(self, widget, message):
        # Usuń nagłówek i stopkę FIXML jeśli są obecne
        if isinstance(message, str) and message.startswith("<FIXML"):
            # Usuwa <FIXML ...> oraz końcowy </FIXML>
            message = re.sub(r'^<FIXML[^>]*>', '', message, flags=re.DOTALL)
            message = re.sub(r'</FIXML>$', '', message, flags=re.DOTALL)
            message = message.strip()
        widget.config(state='normal')
        widget.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        widget.yview(tk.END)
        widget.config(state='disabled')

    def start_login_thread(self):
        self.login_button.config(state='disabled')
        self.disconnect_button.config(state='disabled')
  #      username = self.username_entry.get()
  #      password = self.password_entry.get()
        username="BOS"
        password="BOS"
        if username == "TWOJA_NAZWA_UŻYTKOWNIKA" or password == "TWOJE_HASŁO":
            self.log_message(self.status_log, "BŁĄD: Wprowadź swoje dane logowania.")
            self.login_button.config(state='normal')
            return
        self.client = BossaAPIClient(username, password, self.queue)
        threading.Thread(target=self.client.run, daemon=True).start()

    def add_to_filter(self):
        if self.client:
            self.log_message(self.status_log, f"Wysyłanie żądania dodania {self.TARGET_ISIN} do filtra...")
            threading.Thread(target=self.client.add_to_filter, args=(self.TARGET_ISIN,), daemon=True).start()

    def clear_filter(self):
        if self.client:
            self.log_message(self.status_log, "Wysyłanie żądania wyczyszczenia filtra...")
            threading.Thread(target=self.client.clear_filter, daemon=True).start()

    def disconnect(self):
        if self.client:
            self.log_message(self.status_log, "Rozłączanie...")
            self.disconnect_button.config(state='disabled')
            self.client.disconnect()
            
    def display_portfolio(self, portfolio_data):
        self.portfolio_display.config(state='normal')
        self.portfolio_display.delete('1.0', tk.END)
        formatted_text = ""
        for account, data in portfolio_data.items():
            formatted_text += f"[ RACHUNEK: {account} ]\n"
            formatted_text += "  Środki:\n"
            for fund, value in data.get('funds', {}).items():
                formatted_text += f"    - {fund}: {value}\n"
            formatted_text += "\n  Pozycje:\n"
            positions = data.get('positions', [])
            if positions:
                for pos in positions:
                    formatted_text += f"    - Symbol: {pos['symbol']}, Ilość: {pos['quantity']}, ISIN: {pos['isin']}\n"
            else:
                formatted_text += "    - Brak otwartych pozycji.\n"
            formatted_text += "-"*40 + "\n"
        self.portfolio_display.insert(tk.END, formatted_text)
        self.portfolio_display.config(state='disabled')

class BossaAPIClient:
    def __init__(self, username, password, gui_queue):
        # ...
        self.username = username
        self.password = password
        self.gui_queue = gui_queue
        self.sync_port = None
        self.async_port = None
        self.is_logged_in = False
        self.portfolio = {}
        self.stop_event = threading.Event()
        self.request_id = 1
        self.async_socket = None
        self.market_data = {}
        self.TARGET_ISIN = "PL0GF0031252"
        self.bot_thread = None
        self.bot_stop_event = threading.Event()
        self.bot_state = BotState.STOPPED
        self.bot_params = {}
        self.active_order_id = None
        self.position_entry_price = 0
        self.daily_profit = 0

    def _parse_execution_report(self, xml_data):
        try:
            # ...
            root = ET.fromstring(xml_data)
            exec_rpt = root.find('ExecRpt')
            if exec_rpt is None: return
            
            instrument = exec_rpt.find('Instrmt')
            symbol = instrument.get('Sym', 'N/A') if instrument is not None else 'N/A'
            order_data = {'id_dm': exec_rpt.get('OrdID', ''), 'id_klienta': exec_rpt.get('ID', ''),'status': exec_rpt.get('Stat', ''), 'symbol': symbol, 'k_s': exec_rpt.get('Side', ''), 'ilosc': exec_rpt.find('.//OrdQty').get('Qty', '') if exec_rpt.find('.//OrdQty') is not None else '', 'pozostalo': exec_rpt.get('LeavesQty', ''), 'wykonano': exec_rpt.get('CumQty', ''), 'limit': exec_rpt.get('Px', ''), 'cena_ost': exec_rpt.get('LastPx', ''), 'czas': exec_rpt.get('TxnTm', '')}
            self.gui_queue.put(("EXEC_REPORT", order_data))

            order_id = exec_rpt.get('ID')
            status = exec_rpt.get('Stat')
            if order_id == self.active_order_id and status == '2':
                if self.bot_state == BotState.WAITING_FOR_BUY_FILL:
                    self.position_entry_price = float(exec_rpt.get('LastPx', '0'))
                    self.bot_state = BotState.IN_POSITION
                    self._bot_log(f"Zlecenie KUPNA zrealizowane po cenie {self.position_entry_price}. Stan: W POZYCJI.")
                    
                    # --- Komunikat do GUI o stanie bota ---
                    self.gui_queue.put(("BOT_STATE_UPDATE", {'open_positions': 1, 'entry_price': self.position_entry_price}))

                    profit_price = self.position_entry_price + self.bot_params['profit_points'] + 2 * self.bot_params['commission']
                    self._bot_log(f"Ustawiam zlecenie TAKE-PROFIT na cenę {profit_price:.2f}")
                    self.bot_state = BotState.WAITING_FOR_SELL_FILL
                    threading.Thread(target=self.send_limit_order, args=(self.bot_params['account'], "Sprzedaż", 1, profit_price, True), daemon=True).start()

                elif self.bot_state in [BotState.WAITING_FOR_SELL_FILL, BotState.PANIC_SELLING]:
                    exit_price = float(exec_rpt.get('LastPx', '0'))
                    profit = exit_price - self.position_entry_price - 2 * self.bot_params['commission']
                    self.daily_profit += profit
                    self._bot_log(f"Zlecenie SPRZEDAŻY zrealizowane po {exit_price}. Zysk/Strata: {profit:.2f}. Zysk dzienny: {self.daily_profit:.2f}")
                    self.bot_state = BotState.IDLE
                    
                    # --- Komunikat do GUI o stanie bota ---
                    self.gui_queue.put(("BOT_STATE_UPDATE", {'open_positions': 0, 'entry_price': None}))
        except Exception as e:
            self._log(f"Błąd podczas parsowania ExecutionReport: {e}")

    def _parse_market_data(self, xml_data):
        try:
            # ...
            root = ET.fromstring(xml_data)
            updated_data = {}
            for inc_element in root.findall('.//Inc'):
                entry_type = inc_element.get('Typ')
                instrument = inc_element.find('Instrmt')
                if instrument is not None:
                    isin = instrument.get('ID')
                    if isin not in self.market_data: self.market_data[isin] = {}
                    
                    price_str = inc_element.get('Px')
                    if price_str:
                        price = float(price_str)
                        if entry_type == '0': self.market_data[isin]['bid'] = price
                        elif entry_type == '1': self.market_data[isin]['ask'] = price
                        elif entry_type == '2': self.market_data[isin]['last_price'] = price
            
            # Wyślij jedną zbiorczą aktualizację do GUI
            if self.TARGET_ISIN in self.market_data:
                data_to_send = self.market_data[self.TARGET_ISIN]
                data_to_send['isin'] = self.TARGET_ISIN
                self.gui_queue.put(("MARKET_DATA_UPDATE", data_to_send))

        except Exception as e:
            self._log(f"Błąd podczas parsowania danych rynkowych: {e}")

    # Pozostałe metody bez zmian
    def _bot_log(self, message):
        self.gui_queue.put(("BOT_LOG", message))

    def start_bot(self, params):
        self.bot_params = params
        self.bot_state = BotState.IDLE
        self.daily_profit = 0
        self.bot_stop_event.clear()
        self.bot_thread = threading.Thread(target=self._bot_loop, daemon=True)
        self.bot_thread.start()

    def stop_bot(self):
        self.bot_stop_event.set()
        if self.bot_state == BotState.IN_POSITION:
            self._bot_log("UWAGA: Bot zatrzymany, ale POZYCJA POZOSTAJE OTWARTA!")
        self.bot_state = BotState.STOPPED
    
    def _bot_loop(self):
        self._bot_log("Pętla bota rozpoczęta. Oczekiwanie na sygnały...")
        while not self.bot_stop_event.is_set():
            time.sleep(1)
            
            if self.daily_profit >= self.bot_params['daily_goal']:
                self._bot_log(f"Cel dzienny ({self.daily_profit}) osiągnięty! Zatrzymuję bota.")
                self.gui_queue.put(("BOT_STOPPED", None))
                break

            if self.bot_state == BotState.IDLE:
                market_info = self.market_data.get(self.TARGET_ISIN)
                if not market_info or 'bid' not in market_info or 'ask' not in market_info:
                    continue

                entry_price = market_info['bid']
                self._bot_log(f"Stan IDLE. Wykryto cenę BID: {entry_price}. Składam zlecenie kupna...")
                self.bot_state = BotState.WAITING_FOR_BUY_FILL
                threading.Thread(target=self.send_limit_order, args=(self.bot_params['account'], "Kupno", 1, entry_price, True), daemon=True).start()

            if self.bot_state == BotState.IN_POSITION:
                market_info = self.market_data.get(self.TARGET_ISIN)
                if not market_info or 'last_price' not in market_info:
                    continue
                
                current_price = market_info['last_price']
                stop_loss_price = self.position_entry_price - self.bot_params['stop_loss_points']
                
                if current_price <= stop_loss_price:
                    self._bot_log(f"STOP-LOSS! Cena {current_price} <= {stop_loss_price}. Sprzedaż natychmiastowa...")
                    self.bot_state = BotState.PANIC_SELLING
                    threading.Thread(target=self.send_limit_order, args=(self.bot_params['account'], "Sprzedaż", 1, current_price, True), daemon=True).start()

        self._bot_log("Pętla bota zakończona.")
        self.bot_state = BotState.STOPPED

    def send_limit_order(self, account, direction, quantity, price, from_bot=False):
        self.request_id += 1
        client_order_id = self.request_id
        if from_bot:
            self.active_order_id = str(client_order_id)
        
        side = '1' if direction == "Kupno" else '2'
        trade_date = datetime.now().strftime('%Y%m%d')
        transact_time = datetime.now().strftime('%Y%m%d-%H:%M:%S')
        order_type = 'L'
        time_in_force = '0'

        fixml_request = f"""<FIXML v="5.0" r="20080317" s="20080314"><Order ID="{client_order_id}" TrdDt="{trade_date}" Acct="{account}" Side="{side}" TxnTm="{transact_time}" OrdTyp="{order_type}" Px="{price:.2f}" Ccy="PLN" TmInForce="{time_in_force}"><Instrmt ID="{self.TARGET_ISIN}" Src="4"/><OrdQty Qty="{quantity}"/></Order></FIXML>"""
        response = self._send_and_receive_sync(fixml_request)

        if response and '<ExecRpt' in response:
            self._parse_execution_report(response)
        elif response:
             self._log(f"Odrzucenie zlecenia. Odpowiedź: {response}")
        else:
            self._log("Brak odpowiedzi serwera na zlecenie.")

    def _log(self, message):
        self.gui_queue.put(("LOG", message))

    def _send_and_receive_sync(self, message):
        sync_socket = None
        try:
            sync_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sync_socket.connect(('127.0.0.1', self.sync_port))
            self._send_message(sync_socket, message)
            response = self._receive_message(sync_socket)
            return response
        except ConnectionAbortedError as e:
            self._log(f"BŁĄD: Połączenie zostało zerwane przez serwer (NOL3). {e}")
            return None
        except Exception as e:
            self._log(f"BŁĄD komunikacji synchronicznej: {e}")
            return None
        finally:
            if sync_socket:
                sync_socket.close()

    def add_to_filter(self, isin):
        self.request_id += 1
        fixml_request = f'<FIXML v="5.0" r="20080317" s="20080314"><MktDataReq ReqID="{self.request_id}" SubReqTyp="1" MktDepth="0"><req Typ="0"/><req Typ="1"/><req Typ="2"/><req Typ="B"/><req Typ="C"/><req Typ="3"/><req Typ="4"/><req Typ="5"/><req Typ="7"/><req Typ="r"/><req Typ="8"/><InstReq><Instrmt ID="{isin}" Src="4"/></InstReq></MktDataReq></FIXML>'
        response = self._send_and_receive_sync(fixml_request)
        if response and '<MktDataFull' in response:
            self._log(f"Pomyślnie dodano {isin} do filtra.")
        else:
            self._log(f"Błąd podczas dodawania do filtra. Odpowiedź: {response}")

    def clear_filter(self):
        self.request_id += 1
        fixml_request = f'<FIXML v="5.0" r="20080317" s="20080314"><MktDataReq ReqID="{self.request_id}" SubReqTyp="2"></MktDataReq></FIXML>'
        response = self._send_and_receive_sync(fixml_request)
        if response and '<MktDataFull' in response:
            self._log("Pomyślnie wyczyszczono filtr.")
        else:
            self._log(f"Błąd podczas czyszczenia filtra. Odpowiedź: {response}")

    def _async_listener(self):
        try:
            self.async_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.async_socket.connect(('127.0.0.1', self.async_port))
            self._log("Połączono z portem asynchronicznym.")
            while not self.stop_event.is_set():
                message = self._receive_message(self.async_socket)
                if message is None: break
                self.gui_queue.put(("ASYNC_MSG", message))
                if '<ExecRpt' in message: self._parse_execution_report(message)
                elif '<MktDataInc' in message: self._parse_market_data(message)
                elif '<Statement' in message:
                    self._parse_portfolio(message)
                    self.gui_queue.put(("PORTFOLIO", self.portfolio))
        except Exception as e:
            if not self.stop_event.is_set(): self._log(f"Błąd w wątku asynchronicznym: {e}")
        finally:
            if self.async_socket: self.async_socket.close()
            
    def run(self):
        if not self._get_ports_from_registry():
            self.gui_queue.put(("LOGIN_FAIL", "Błąd odczytu portów z rejestru."))
            return
        self.request_id += 1
        login_request = f'<FIXML v="5.0" r="20080317" s="20080314"><UserReq UserReqID="{self.request_id}" UserReqTyp="1" Username="{self.username}" Password="{self.password}"/></FIXML>'
        self._log("Wysyłanie żądania logowania...")
        response = self._send_and_receive_sync(login_request)
        if response and '<UserRsp' in response:
            root = ET.fromstring(response)
            user_rsp = root.find('UserRsp')
            if user_rsp is not None and user_rsp.get('UserStat') == '1':
                self.is_logged_in = True
                self.gui_queue.put(("LOGIN_SUCCESS", None))
                self._async_listener()
            else:
                status = user_rsp.get('UserStat') if user_rsp is not None else 'brak'
                self.gui_queue.put(("LOGIN_FAIL", f"Status: {status}"))
        else:
            self.gui_queue.put(("LOGIN_FAIL", f"Nieoczekiwana odpowiedź: {response}"))

    def disconnect(self):
        self.stop_bot()
        self.stop_event.set()
        if self.async_socket:
            try:
                self.async_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            finally:
                self.async_socket.close()
        self.gui_queue.put(("DISCONNECTED", None))

    def _get_ports_from_registry(self):
        try:
            key_path = r"Software\COMARCH S.A.\NOL3\7\Settings"
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            self.sync_port, _ = winreg.QueryValueEx(registry_key, "nca_psync")
            self.async_port, _ = winreg.QueryValueEx(registry_key, "nca_pasync")
            self.sync_port = int(self.sync_port)
            self.async_port = int(self.async_port)  # Konwersja do int
            winreg.CloseKey(registry_key)
            self._log(f"Odczytano porty: Sync={self.sync_port}, Async={self.async_port}")
            return True
        except FileNotFoundError:
            self._log("BŁĄD: Nie znaleziono klucza rejestru bossaNOL3.")
            return False
        except Exception as e:
            self._log(f"BŁĄD podczas odczytu rejestru: {e}")
            return False

    def _send_message(self, sock, message):
        encoded_message = message.encode('utf-8')
        header = struct.pack('<I', len(encoded_message))
        sock.sendall(header)
        sock.sendall(encoded_message)

    def _receive_message(self, sock):
        header_data = sock.recv(4)
        if not header_data: return None
        message_length = struct.unpack('<I', header_data)[0]
        if message_length == 0: return ""
        message_data = b''
        while len(message_data) < message_length:
            chunk = sock.recv(message_length - len(message_data))
            if not chunk: raise ConnectionError("Przerwano połączenie.")
            message_data += chunk
        return message_data.decode('utf-8','replace').strip().rstrip('\x00')

    def _parse_portfolio(self, xml_data):
        root = ET.fromstring(xml_data)
        for statement in root.findall('Statement'):
            account_id = statement.get('Acct')
            self.portfolio[account_id] = {'funds': {}, 'positions': []}
            for fund in statement.findall('Fund'):
                self.portfolio[account_id]['funds'][fund.get('name')] = fund.get('value')
            for position in statement.findall('.//Position'):
                instrument = position.find('Instrmt')
                self.portfolio[account_id]['positions'].append({
                    'symbol': instrument.get('Sym'), 'isin': instrument.get('ID'),
                    'quantity': position.get('Acc110'), 'blocked_quantity': position.get('Acc120')
                })

if __name__ == '__main__':
    root = tk.Tk()
    app = BossaApp(root)
    root.mainloop()