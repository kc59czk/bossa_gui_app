import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import random
from datetime import datetime
import threading
import queue
import socket
import struct
import winreg
import xml.etree.ElementTree as ET
import time
import re

class ScalpingBot:
    def __init__(self):
        self.commission = 2  # 2 points commission per trade
        self.daily_goal = 20  # 20 points daily goal
        self.current_profit = 0
        self.trades = []
        self.is_running = False
        self.balance = 10000  # Starting balance
        self.contract_size = 1  # Trading 1 future contract
        
    def calculate_profit(self, entry_price, exit_price, quantity, is_long):
        # Calculate profit considering commission
        price_diff = exit_price - entry_price if is_long else entry_price - exit_price
        profit = price_diff * quantity - self.commission
        return profit

class BossaAPIClient:
    def __init__(self, username, password, gui_queue):
        self.username = username
        self.password = password
        self.gui_queue = gui_queue
        self.sync_port = None
        self.async_port = None
        self.sync_socket = None
        self.async_socket = None
        self.is_logged_in = False
        self.portfolio = {}
        self.stop_event = threading.Event()
        self.request_id = 200
        self.sync_lock = threading.Lock()  # Zabezpieczenie dostępu do socketu synchronicznego

    def _log(self, message):
        self.gui_queue.put(("LOG", message))

    def _send_and_receive_sync(self, message):
        """
        Nawiązuje nowe połączenie, wysyła wiadomość, odbiera odpowiedź i zamyka połączenie.
        Jest to najbardziej niezawodny sposób komunikacji synchronicznej z tym API.
        """
        sync_socket = None
        try:
            # 1. Zawsze twórz nowy socket i łącz się
            sync_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sync_socket.connect(('127.0.0.1', self.sync_port))
            
            # 2. Wysyłaj i odbieraj dane
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
            # 3. Zawsze zamykaj socket po zakończeniu operacji
            if sync_socket:
                sync_socket.close()

    def add_to_filter(self, isin):
        """Wysyła żądanie dodania instrumentu do filtra."""
        self.request_id += 1
        # Komunikat zgodny z przykładem w dokumentacji [cite: 210]
        # Atrybuty SubReqTyp="1" i MktDepth="0" [cite: 207]
        fixml_request = f"""<FIXML v="5.0" r="20080317" s="20080314">
<MktDataReq ReqID="{self.request_id}" SubReqTyp="1" MktDepth="0">
<req Typ="0"/><req Typ="1"/><req Typ="2"/><req Typ="B"/>
<req Typ="C"/><req Typ="3"/><req Typ="4"/><req Typ="5"/>
<req Typ="7"/><req Typ="r"/><req Typ="8"/>
<InstReq><Instrmt ID="{isin}" Src="4"/></InstReq>
</MktDataReq></FIXML>"""
        
        response = self._send_and_receive_sync(fixml_request)
        
        if response and '<MktDataFull' in response:  # Odpowiedź synchroniczna to MarketDataSnapshotFullRefresh [cite: 217]
            self._log(f"Pomyślnie dodano {isin} do filtra.")
        else:
            self._log(f"Błąd podczas dodawania do filtra. Odpowiedź: {response}")

    def clear_filter(self):
        """Wysyła żądanie wyczyszczenia filtra."""
        self.request_id += 1
        # Atrybut SubReqTyp="2" do czyszczenia filtra [cite: 207]
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
                if message is None: 
                    break
                
                # Przekazujemy KAŻDY surowy komunikat do GUI
                self.gui_queue.put(("ASYNC_MSG", message))

                # Dodatkowo, jeśli to wyciąg, parsujemy go dla okna portfela
                if '<Statement' in message:
                    self._parse_portfolio(message)
                    self.gui_queue.put(("PORTFOLIO", self.portfolio))
        except Exception as e:
            if not self.stop_event.is_set():
                self._log(f"Błąd w wątku asynchronicznym: {e}")
        finally:
            if self.async_socket: 
                self.async_socket.close()
            
    def run(self):
        if not self._get_ports_from_registry():
            self.gui_queue.put(("LOGIN_FAIL", "Błąd odczytu portów z rejestru."))
            return

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
            elif user_rsp.get('UserStat') == '6':
                self.gui_queue.put(("LOGIN_SUCCESS", f"Status: {user_rsp.get('UserStat')}"))
                self.is_logged_in = True
                self._async_listener()
            else:
                status = user_rsp.get('UserStat') if user_rsp is not None else 'brak'
                self.gui_queue.put(("LOGIN_FAIL", f"Status: {status}"))
        else:
            self.gui_queue.put(("LOGIN_FAIL", f"Nieoczekiwana odpowiedź: {response}"))
            if self.sync_socket: 
                self.sync_socket.close()
            self.sync_socket = None

    def disconnect(self):
        self.stop_event.set()
        # Delikatne zamknięcie socketu asynchronicznego, aby przerwać pętlę recv
        if self.async_socket:
            self.async_socket.shutdown(socket.SHUT_RDWR)
            self.async_socket.close()
        if self.sync_socket:
            self.sync_socket.close()
            self.sync_socket = None
        self.gui_queue.put(("DISCONNECTED", None))

    def _get_ports_from_registry(self):
        try:
            key_path = r"Software\COMARCH S.A.\NOL3\7\Settings"
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            self.sync_port, _ = winreg.QueryValueEx(registry_key, "nca_psync")
            self.async_port, _ = winreg.QueryValueEx(registry_key, "nca_pasync")
            self.sync_port = int(self.sync_port)
            self.async_port = int(self.async_port)
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
        try:
            header_data = sock.recv(4)
            if not header_data: 
                return None
            message_length = struct.unpack('<I', header_data)[0]
            if message_length == 0: 
                return ""
            message_data = b''
            while len(message_data) < message_length:
                chunk = sock.recv(message_length - len(message_data))
                if not chunk: 
                    raise ConnectionError("Przerwano połączenie.")
                message_data += chunk
            return message_data.decode('utf-8','replace').strip().rstrip('\x00')
        except:
            return None

    def _parse_portfolio(self, xml_data):
        try:
            root = ET.fromstring(xml_data)
            for statement in root.findall('Statement'):
                account_id = statement.get('Acct')
                self.portfolio[account_id] = {'funds': {}, 'positions': []}
                for fund in statement.findall('Fund'):
                    self.portfolio[account_id]['funds'][fund.get('name')] = fund.get('value')
                for position in statement.findall('.//Position'):
                    instrument = position.find('Instrmt')
                    if instrument is not None:
                        self.portfolio[account_id]['positions'].append({
                            'symbol': instrument.get('Sym'), 'isin': instrument.get('ID'),
                            'quantity': position.get('Acc110'), 'blocked_quantity': position.get('Acc120')
                        })
        except Exception as e:
            self._log(f"Błąd parsowania portfolio: {e}")

class ScalpingBotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Warsaw Stock Exchange Scalping Bot with BossaAPI")
        self.root.geometry("1000x800")
        self.root.configure(bg='#2c3e50')
        
        # Initialize bot and current price
        self.bot = ScalpingBot()
        self.current_price = 4500.0  # Initialize current_price here
        
        # BossaAPI client
        self.client = None
        self.queue = queue.Queue()
        
        # Create notebook (tab container)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create frames for tabs
        self.create_dashboard_tab()
        self.create_trading_tab()
        self.create_settings_tab()
        self.create_logs_tab()
        self.create_bossa_tab()
        
        # Start price simulation and queue processing
        self.update_price()
        self.process_queue()
        
    def create_dashboard_tab(self):
        # Create frame for dashboard tab
        dashboard_frame = ttk.Frame(self.notebook, padding="10")
        dashboard_frame.pack(fill='both', expand=True)
        
        # Dashboard title
        title_label = ttk.Label(dashboard_frame, text="Trading Dashboard", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(dashboard_frame, text="Performance Metrics", padding="10")
        stats_frame.pack(fill='x', pady=10)
        
        # Stats labels
        ttk.Label(stats_frame, text="Current Balance:").grid(row=0, column=0, sticky='w', pady=5)
        self.balance_var = tk.StringVar(value=f"${self.bot.balance:,.2f}")
        ttk.Label(stats_frame, textvariable=self.balance_var, font=('Arial', 12, 'bold')).grid(row=0, column=1, sticky='w', pady=5)
        
        ttk.Label(stats_frame, text="Today's Profit:").grid(row=1, column=0, sticky='w', pady=5)
        self.profit_var = tk.StringVar(value=f"{self.bot.current_profit} points")
        ttk.Label(stats_frame, textvariable=self.profit_var, font=('Arial', 12, 'bold')).grid(row=1, column=1, sticky='w', pady=5)
        
        ttk.Label(stats_frame, text="Daily Goal:").grid(row=2, column=0, sticky='w', pady=5)
        ttk.Label(stats_frame, text=f"{self.bot.daily_goal} points", font=('Arial', 12)).grid(row=2, column=1, sticky='w', pady=5)
        
        ttk.Label(stats_frame, text="Commission:").grid(row=3, column=0, sticky='w', pady=5)
        ttk.Label(stats_frame, text=f"{self.bot.commission} points per trade", font=('Arial', 12)).grid(row=3, column=1, sticky='w', pady=5)
        
        # Progress towards goal
        ttk.Label(stats_frame, text="Goal Progress:").grid(row=4, column=0, sticky='w', pady=5)
        self.progress = ttk.Progressbar(stats_frame, orient='horizontal', length=200, mode='determinate')
        self.progress.grid(row=4, column=1, sticky='w', pady=5)
        self.update_progress()
        
        # Current price frame
        price_frame = ttk.LabelFrame(dashboard_frame, text="Current Price", padding="10")
        price_frame.pack(fill='x', pady=10)
        
        ttk.Label(price_frame, text="FUTURES INDEX:").grid(row=0, column=0, sticky='w', pady=5)
        self.price_var = tk.StringVar(value=f"{self.current_price:.2f}")
        price_label = ttk.Label(price_frame, textvariable=self.price_var, font=('Arial', 20, 'bold'))
        price_label.grid(row=0, column=1, sticky='w', pady=5, padx=10)
        
        self.price_change_var = tk.StringVar(value="→")
        self.price_change_label = ttk.Label(price_frame, textvariable=self.price_change_var, font=('Arial', 16))
        self.price_change_label.grid(row=0, column=2, sticky='w', pady=5)
        
        # Bot control frame
        control_frame = ttk.Frame(dashboard_frame)
        control_frame.pack(pady=20)
        
        self.start_button = ttk.Button(control_frame, text="Start Bot", command=self.toggle_bot)
        self.start_button.pack(side='left', padx=10)
        
        ttk.Button(control_frame, text="Reset Day", command=self.reset_day).pack(side='left', padx=10)
        
        # Add the frame to the notebook
        self.notebook.add(dashboard_frame, text="Dashboard")
        
    def create_trading_tab(self):
        # Create frame for trading tab
        trading_frame = ttk.Frame(self.notebook, padding="10")
        trading_frame.pack(fill='both', expand=True)
        
        # Trading title
        title_label = ttk.Label(trading_frame, text="Trading Parameters", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Strategy settings
        strategy_frame = ttk.LabelFrame(trading_frame, text="Trading Strategy", padding="10")
        strategy_frame.pack(fill='x', pady=10)
        
        ttk.Label(strategy_frame, text="Entry Threshold (points):").grid(row=0, column=0, sticky='w', pady=5)
        self.entry_threshold = ttk.Entry(strategy_frame)
        self.entry_threshold.insert(0, "5")
        self.entry_threshold.grid(row=0, column=1, sticky='w', pady=5, padx=5)
        
        ttk.Label(strategy_frame, text="Stop Loss (points):").grid(row=1, column=0, sticky='w', pady=5)
        self.stop_loss = ttk.Entry(strategy_frame)
        self.stop_loss.insert(0, "10")
        self.stop_loss.grid(row=1, column=1, sticky='w', pady=5, padx=5)
        
        ttk.Label(strategy_frame, text="Take Profit (points):").grid(row=2, column=0, sticky='w', pady=5)
        self.take_profit = ttk.Entry(strategy_frame)
        self.take_profit.insert(0, "8")
        self.take_profit.grid(row=2, column=1, sticky='w', pady=5, padx=5)
        
        # Manual trade frame
        manual_frame = ttk.LabelFrame(trading_frame, text="Manual Trade", padding="10")
        manual_frame.pack(fill='x', pady=10)
        
        ttk.Button(manual_frame, text="BUY", command=lambda: self.manual_trade(True)).pack(side='left', padx=10)
        ttk.Button(manual_frame, text="SELL", command=lambda: self.manual_trade(False)).pack(side='left', padx=10)
        
        # Add the frame to the notebook
        self.notebook.add(trading_frame, text="Trading")
        
    def create_settings_tab(self):
        # Create frame for settings tab
        settings_frame = ttk.Frame(self.notebook, padding="10")
        settings_frame.pack(fill='both', expand=True)
        
        # Settings title
        title_label = ttk.Label(settings_frame, text="Bot Configuration", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Settings form
        form_frame = ttk.Frame(settings_frame)
        form_frame.pack(fill='both', expand=True, pady=10)
        
        ttk.Label(form_frame, text="Daily Goal (points):").grid(row=0, column=0, sticky='w', pady=10, padx=10)
        self.daily_goal_entry = ttk.Entry(form_frame)
        self.daily_goal_entry.insert(0, str(self.bot.daily_goal))
        self.daily_goal_entry.grid(row=0, column=1, sticky='w', pady=10, padx=10)
        
        ttk.Label(form_frame, text="Commission (points):").grid(row=1, column=0, sticky='w', pady=10, padx=10)
        self.commission_entry = ttk.Entry(form_frame)
        self.commission_entry.insert(0, str(self.bot.commission))
        self.commission_entry.grid(row=1, column=1, sticky='w', pady=10, padx=10)
        
        ttk.Label(form_frame, text="Contract Size:").grid(row=2, column=0, sticky='w', pady=10, padx=10)
        self.contract_size_entry = ttk.Entry(form_frame)
        self.contract_size_entry.insert(0, str(self.bot.contract_size))
        self.contract_size_entry.grid(row=2, column=1, sticky='w', pady=10, padx=10)
        
        ttk.Button(form_frame, text="Save Settings", command=self.save_settings).grid(row=3, column=0, columnspan=2, pady=20)
        
        # Add the frame to the notebook
        self.notebook.add(settings_frame, text="Settings")
        
    def create_logs_tab(self):
        # Create frame for logs tab
        logs_frame = ttk.Frame(self.notebook, padding="10")
        logs_frame.pack(fill='both', expand=True)
        
        # Logs title
        title_label = ttk.Label(logs_frame, text="Trading Activity Log", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Log text area
        self.log_text = tk.Text(logs_frame, height=20, width=80, state='disabled')
        scrollbar = ttk.Scrollbar(logs_frame, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Add the frame to the notebook
        self.notebook.add(logs_frame, text="Activity Log")
        
    def create_bossa_tab(self):
        # Create frame for BossaAPI tab
        bossa_frame = ttk.Frame(self.notebook, padding="10")
        bossa_frame.pack(fill='both', expand=True)
        
        # BossaAPI title
        title_label = ttk.Label(bossa_frame, text="BossaAPI Connection", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Login frame
        login_frame = ttk.Frame(bossa_frame)
        login_frame.pack(fill='x', pady=10)
        
        ttk.Label(login_frame, text="Użytkownik:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.username_entry = tk.Entry(login_frame, width=20)
        self.username_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(login_frame, text="Hasło:").grid(row=0, column=2, sticky="w", padx=5)
        self.password_entry = tk.Entry(login_frame, show="*", width=20)
        self.password_entry.grid(row=0, column=3, sticky="ew", padx=5)
        self.username_entry.insert(0, "BOS")
        self.password_entry.insert(0, "BOS")
        self.login_button = tk.Button(login_frame, text="Połącz i zaloguj", command=self.start_login_thread)
        self.login_button.grid(row=0, column=4, sticky="ew", padx=10)
        self.disconnect_button = tk.Button(login_frame, text="Rozłącz", command=self.disconnect, state='disabled')
        self.disconnect_button.grid(row=0, column=5, sticky="ew", padx=10)
        
        # Filter frame
        filter_frame = ttk.Frame(bossa_frame)
        filter_frame.pack(fill='x', pady=10)
        
        ttk.Label(filter_frame, text="ISIN:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.isin_entry = tk.Entry(filter_frame, width=25)
        self.isin_entry.grid(row=0, column=1, sticky="ew", padx=5)
        self.isin_entry.insert(0, "PL0GF0031252")
        self.add_filter_button = tk.Button(filter_frame, text="Dodaj do filtra", command=self.add_to_filter, state='disabled')
        self.add_filter_button.grid(row=0, column=2, padx=5)
        self.clear_filter_button = tk.Button(filter_frame, text="Wyczyść filtr", command=self.clear_filter, state='disabled')
        self.clear_filter_button.grid(row=0, column=3, padx=5)
        
        # Status log
        ttk.Label(bossa_frame, text="Status log:").pack(anchor='w', pady=(10, 0))
        self.status_log = scrolledtext.ScrolledText(bossa_frame, height=8, state='disabled')
        self.status_log.pack(fill='both', expand=True, pady=(0, 5))
        
        # Async messages
        ttk.Label(bossa_frame, text="Surowe komunikaty async:").pack(anchor='w', pady=(10, 0))
        self.async_messages = scrolledtext.ScrolledText(bossa_frame, height=8, state='disabled', bg='lightgrey')
        self.async_messages.pack(fill='both', expand=True)
        
        # Add the frame to the notebook
        self.notebook.add(bossa_frame, text="BossaAPI")
        
    def update_price(self):
        if hasattr(self, 'price_var'):
            # Simulate price changes
            change = random.uniform(-5, 5)
            self.current_price += change
            self.price_var.set(f"{self.current_price:.2f}")
            
            # Update change indicator
            if change > 0.1:
                self.price_change_var.set("↑")
                self.price_change_label.configure(foreground='green')
            elif change < -0.1:
                self.price_change_var.set("↓")
                self.price_change_label.configure(foreground='red')
            else:
                self.price_change_var.set("→")
                self.price_change_label.configure(foreground='gray')
            
            # Simulate trades if bot is running
            if self.bot.is_running:
                self.simulate_trade()
            
        # Schedule next update
        self.root.after(1000, self.update_price)
        
    def simulate_trade(self):
        # Simulate random trading decisions (in a real bot, this would be based on strategy)
        if random.random() < 0.3:  # 30% chance of making a trade each second
            is_long = random.random() < 0.5  # Randomly choose long or short
            entry_price = self.current_price
            exit_price = entry_price + random.uniform(2, 10) * (1 if is_long else -1)
            quantity = self.bot.contract_size
            
            profit = self.bot.calculate_profit(entry_price, exit_price, quantity, is_long)
            self.bot.current_profit += profit
            self.bot.balance += profit * 10  # Assuming 1 point = $10
            
            # Record trade
            trade = {
                'time': datetime.now().strftime("%H:%M:%S"),
                'type': 'LONG' if is_long else 'SHORT',
                'entry': entry_price,
                'exit': exit_price,
                'quantity': quantity,
                'profit': profit
            }
            self.bot.trades.append(trade)
            
            # Update UI
            self.update_progress()
            self.log_trade(trade)
            
            # Check if daily goal is reached
            if self.bot.current_profit >= self.bot.daily_goal:
                self.bot.is_running = False
                self.start_button.config(text="Start Bot")
                self.log_message("Daily goal reached! Bot stopped.")
                
    def manual_trade(self, is_long):
        entry_price = self.current_price
        # For simulation, assume a fixed exit price
        exit_price = entry_price + (5 if is_long else -5)
        quantity = self.bot.contract_size
        
        profit = self.bot.calculate_profit(entry_price, exit_price, quantity, is_long)
        self.bot.current_profit += profit
        self.bot.balance += profit * 10  # Assuming 1 point = $10
        
        # Record trade
        trade = {
            'time': datetime.now().strftime("%H:%M:%S"),
            'type': 'LONG' if is_long else 'SHORT',
            'entry': entry_price,
            'exit': exit_price,
            'quantity': quantity,
            'profit': profit
        }
        self.bot.trades.append(trade)
        
        # Update UI
        self.update_progress()
        self.log_trade(trade)
        
    def update_progress(self):
        # Update progress bar
        progress_percent = (self.bot.current_profit / self.bot.daily_goal) * 100
        self.progress['value'] = min(progress_percent, 100)
        
        # Update labels
        self.profit_var.set(f"{self.bot.current_profit:.2f} points")
        self.balance_var.set(f"${self.bot.balance:,.2f}")
        
    def log_trade(self, trade):
        self.log_message(
            f"{trade['time']} - {trade['type']} - "
            f"Entry: {trade['entry']:.2f} - "
            f"Exit: {trade['exit']:.2f} - "
            f"Profit: {trade['profit']:.2f} points"
        )
        
    def log_message(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert('end', message + '\n')
        self.log_text.see('end')
        self.log_text.config(state='disabled')
        
    def toggle_bot(self):
        self.bot.is_running = not self.bot.is_running
        if self.bot.is_running:
            self.start_button.config(text="Stop Bot")
            self.log_message("Bot started - beginning to scan for opportunities...")
        else:
            self.start_button.config(text="Start Bot")
            self.log_message("Bot stopped")
            
    def reset_day(self):
        self.bot.current_profit = 0
        self.bot.trades = []
        self.update_progress()
        self.log_message("Day reset - all profits and trades cleared")
        
    def save_settings(self):
        try:
            self.bot.daily_goal = int(self.daily_goal_entry.get())
            self.bot.commission = int(self.commission_entry.get())
            self.bot.contract_size = int(self.contract_size_entry.get())
            self.update_progress()
            self.log_message("Settings saved successfully")
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for all settings")
            
    # BossaAPI methods
    def log_bossa_message(self, widget, message):
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
        username = self.username_entry.get()
        password = self.password_entry.get()
        if username == "TWOJA_NAZWA_UŻYTKOWNIKA" or password == "TWOJE_HASŁO":
            self.log_bossa_message(self.status_log, "BŁĄD: Wprowadź swoje dane logowania.")
            self.login_button.config(state='normal')
            return
        self.client = BossaAPIClient(username, password, self.queue)
        threading.Thread(target=self.client.run, daemon=True).start()
        
    def process_queue(self):
        try:
            message_type, data = self.queue.get_nowait()
            if message_type == "LOG":
                self.log_bossa_message(self.status_log, data)
            elif message_type == "LOGIN_SUCCESS":
                self.log_bossa_message(self.status_log, f"Logowanie udane! Możesz zarządzać filtrem. INFO: {data}")
                self.disconnect_button.config(state='normal')
                self.add_filter_button.config(state='normal')
                self.clear_filter_button.config(state='normal')
            elif message_type == "ASYNC_MSG":
                # Heartbeat detection (assuming heartbeat contains <HrtBt or similar)
                if "<Heartbeat" in data:
                    pass  # We could add heartbeat visualization here
                else:
                    self.log_bossa_message(self.async_messages, data.strip())
            elif message_type == "PORTFOLIO":
                self.log_bossa_message(self.status_log, "Otrzymano dane portfela.")
                # We could display portfolio data here
            elif message_type == "DISCONNECTED":
                self.log_bossa_message(self.status_log, "Rozłączono.")
                self.login_button.config(state='normal')
                self.disconnect_button.config(state='disabled')
                self.add_filter_button.config(state='disabled')
                self.clear_filter_button.config(state='disabled')
                self.client = None
            elif message_type == "LOGIN_FAIL":
                self.log_bossa_message(self.status_log, f"Logowanie nie powiodło się: {data}")
                self.login_button.config(state='normal')
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)
            
    def add_to_filter(self):
        isin = self.isin_entry.get()
        if self.client and isin:
            self.log_bossa_message(self.status_log, f"Wysyłanie żądania dodania {isin} do filtra...")
            threading.Thread(target=self.client.add_to_filter, args=(isin,), daemon=True).start()
            
    def clear_filter(self):
        if self.client:
            self.log_bossa_message(self.status_log, "Wysyłanie żądania wyczyszczenia filtra...")
            threading.Thread(target=self.client.clear_filter, daemon=True).start()
            
    def disconnect(self):
        if self.client:
            self.log_bossa_message(self.status_log, "Rozłączanie...")
            self.disconnect_button.config(state='disabled')
            self.client.disconnect()

if __name__ == "__main__":
    root = tk.Tk()
    app = ScalpingBotApp(root)
    root.mainloop()