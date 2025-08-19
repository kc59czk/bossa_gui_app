import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import socket
import struct
import winreg
import xml.etree.ElementTree as ET
import time
import re
from datetime import datetime

class BossaApp:
    """Główna klasa aplikacji GUI, która zarządza interfejsem i klientem API."""
    def __init__(self, root):
        self.root = root
        self.root.title("BossaAPI Klient dla PL0GF0031252")
        self.root.geometry("800x850")

        self.client = None
        self.queue = queue.Queue()
        self.TARGET_ISIN = "PL0GF0031252"

        self.create_widgets()
        self.process_queue()

    def create_widgets(self):
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        login_frame = tk.Frame(self.main_frame)
        login_frame.pack(fill='x', pady=(0, 5))

        # --- LOGIN SECTION (add this!) ---
        tk.Label(login_frame, text="Użytkownik:").pack(side='left', padx=(0, 5))
        self.username_entry = tk.Entry(login_frame, width=20)
        self.username_entry.pack(side='left', padx=5)
        tk.Label(login_frame, text="Hasło:").pack(side='left', padx=5)
        self.password_entry = tk.Entry(login_frame, show="*", width=20)
        self.password_entry.pack(side='left', padx=5)
        self.username_entry.insert(0, "BOS")
        self.password_entry.insert(0, "BOS")
        self.login_button = tk.Button(login_frame, text="Połącz i zaloguj", command=self.start_login_thread)
        self.login_button.pack(side='left', padx=10)
        self.disconnect_button = tk.Button(login_frame, text="Rozłącz", command=self.disconnect, state='disabled')
        self.disconnect_button.pack(side='left', padx=10)

        filter_frame = tk.Frame(self.main_frame, relief='groove', borderwidth=2, padx=5, pady=5)
        filter_frame.pack(fill='x', pady=5)
        tk.Label(filter_frame, text=f"Filtr notowań dla {self.TARGET_ISIN}:", font=('Helvetica', 10, 'bold')).pack(side='left', padx=(0, 10))
        self.add_filter_button = tk.Button(filter_frame, text=f"Dodaj {self.TARGET_ISIN} do filtra", command=self.add_to_filter, state='disabled')
        self.add_filter_button.pack(side='left', padx=5)
        self.clear_filter_button = tk.Button(filter_frame, text="Wyczyść filtr", command=self.clear_filter, state='disabled')
        self.clear_filter_button.pack(side='left', padx=5)

        order_frame = tk.Frame(self.main_frame, relief='groove', borderwidth=2, padx=5, pady=5)
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

        # --- Notebook for logs, async logs, and portfolio ---
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill='both', expand=True, pady=5)

        # Tab 1: Status log
        self.tab_status = tk.Frame(self.notebook)
        self.notebook.add(self.tab_status, text="Log statusu")
        tk.Label(self.tab_status, text="Log statusu:").pack(anchor='w')
        self.status_log = scrolledtext.ScrolledText(self.tab_status, height=8, state='disabled')
        self.status_log.pack(fill='both', expand=True, pady=(0, 5))

        # Tab 2: Async logs
        self.tab_async = tk.Frame(self.notebook)
        self.notebook.add(self.tab_async, text="Surowe komunikaty async")
        tk.Label(self.tab_async, text="Surowe komunikaty (kanał asynchroniczny):").pack(anchor='w')
        self.async_messages = scrolledtext.ScrolledText(self.tab_async, height=12, state='disabled', bg='lightgrey')
        self.async_messages.pack(fill='both', expand=True)

        # Tab 3: Portfolio
        self.tab_portfolio = tk.Frame(self.notebook)
        self.notebook.add(self.tab_portfolio, text="Dane portfela")
        tk.Label(self.tab_portfolio, text="Dane portfela:").pack(anchor='w')
        self.portfolio_display = scrolledtext.ScrolledText(self.tab_portfolio, height=10, state='disabled')
        self.portfolio_display.pack(fill='both', expand=True)

        # --- Status bar at the bottom ---
        self.status_frame = tk.Frame(self.root, relief="sunken", bd=1)
        self.status_frame.pack(side="bottom", fill="x")
        self.heartbeat_var = tk.StringVar(value="♡")
        self.status_time_var = tk.StringVar()
        self.status_label = tk.Label(self.status_frame, textvariable=self.heartbeat_var, width=2, fg="red", font=("Arial", 12, "bold"))
        self.status_label.pack(side="left", padx=(5, 2))
        self.status_time_label = tk.Label(self.status_frame, textvariable=self.status_time_var, font=("Arial", 10))
        self.status_time_label.pack(side="left", padx=5)
        self._update_status_time()

    def _flash_heartbeat(self):
        # Flash the heartbeat icon
        self.heartbeat_var.set("❤")
        self.status_label.after(300, lambda: self.heartbeat_var.set("♡"))

    def _update_status_time(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.status_time_var.set(f"Czas: {now}")
        self.root.after(1000, self._update_status_time)

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
    
    def process_queue(self):
        try:
            message_type, data = self.queue.get_nowait()
            if message_type == "LOG":
                self.log_message(self.status_log, data)
            elif message_type == "PRICE_UPDATE":
                if data['isin'] == self.TARGET_ISIN:
                    focused = self.root.focus_get()
                    # Only update if focus is NOT on any widget inside main_frame
                    if not (focused and str(focused).startswith(str(self.main_frame))):
                        self.price_entry.delete(0, tk.END)
                        self.price_entry.insert(0, str(data['price']))
            elif message_type == "LOGIN_SUCCESS":
                self.log_message(self.status_log, f"Logowanie udane! Dodaj {self.TARGET_ISIN} do filtra, aby otrzymywać ceny.")
                self.disconnect_button.config(state='normal')
                self.add_filter_button.config(state='normal')
                self.clear_filter_button.config(state='normal')
                self.send_order_button.config(state='normal')
            elif message_type == "ASYNC_MSG":

                # Heartbeat detection (assuming heartbeat contains <HrtBt or similar)
                if "<Heartbeat" in data:
                    self._flash_heartbeat()
                else:
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
                self.client = None
            elif message_type == "LOGIN_FAIL":
                self.log_message(self.status_log, f"Logowanie nie powiodło się: {data}")
                self.login_button.config(state='normal')

        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

    def add_to_filter(self):
        if self.client:
            self.log_message(self.status_log, f"Wysyłanie żądania dodania {self.TARGET_ISIN} do filtra...")
            threading.Thread(target=self.client.add_to_filter, args=(self.TARGET_ISIN,), daemon=True).start()

    # Pozostałe metody bez zmian

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
        username = self.username_entry.get()
        password = self.password_entry.get()
        if username == "TWOJA_NAZWA_UŻYTKOWNIKA" or password == "TWOJE_HASŁO":
            self.log_message(self.status_log, "BŁĄD: Wprowadź swoje dane logowania.")
            self.login_button.config(state='normal')
            return
        self.client = BossaAPIClient(username, password, self.queue)
        threading.Thread(target=self.client.run, daemon=True).start()

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


# ----------------------------------------------------------------------------- 
# KLASA BossaAPIClient - ZAKTUALIZOWANA O NOWĄ LOGIKĘ ZLECEŃ
# ----------------------------------------------------------------------------- 

class BossaAPIClient:
    def __init__(self, username, password, gui_queue):
        # ... (reszta atrybutów bez zmian)
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

    def send_limit_order(self, account, direction, quantity, price):
        """Wysyła zlecenie LIMIT z ceną podaną przez użytkownika."""
        self.request_id += 1
        client_order_id = self.request_id
        
        side = '1' if direction == "Kupno" else '2'
        trade_date = datetime.now().strftime('%Y%m%d')
        transact_time = datetime.now().strftime('%Y%m%d-%H:%M:%S')
        order_type = 'L' # 'L' = Limit
        time_in_force = '0' # '0' = Dzień

        fixml_request = f"""<FIXML v="5.0" r="20080317" s="20080314">
<Order ID="{client_order_id}" TrdDt="{trade_date}" Acct="{account}" Side="{side}" TxnTm="{transact_time}" OrdTyp="{order_type}" Px="{price}" Ccy="PLN" TmInForce="{time_in_force}">
<Instrmt ID="{self.TARGET_ISIN}" Src="4"/>
<OrdQty Qty="{quantity}"/>
</Order></FIXML>"""

        response = self._send_and_receive_sync(fixml_request)

        if response and '<ExecRpt' in response:
            try:
                root = ET.fromstring(response)
                exec_rpt = root.find('ExecRpt')
                order_status = exec_rpt.get('Stat', 'brak')
                dm_order_id = exec_rpt.get('OrdID', 'brak')
                self._log(f"Zlecenie przyjęte przez DM BOŚ. ID: {dm_order_id}, Status: {order_status}.")
            except Exception as e:
                self._log(f"Otrzymano ExecRpt, ale wystąpił błąd parsowania: {e}. Odpowiedź: {response}")
        elif response:
             self._log(f"Odrzucenie zlecenia. Odpowiedź: {response}")
        else:
            self._log("Brak odpowiedzi serwera na zlecenie.")

    def _parse_market_data(self, xml_data):
        try:
            root = ET.fromstring(xml_data)
            for inc_element in root.findall('.//Inc'):
                entry_type = inc_element.get('Typ')
                if entry_type == '2': # '2' = Trade
                    price_str = inc_element.get('Px')
                    instrument = inc_element.find('Instrmt')
                    if instrument is not None and price_str is not None:
                        isin = instrument.get('ID')
                        price = float(price_str)
                        if isin not in self.market_data: self.market_data[isin] = {}
                        self.market_data[isin]['last_price'] = price
                        # Przekaż aktualizację ceny do GUI
                        self.gui_queue.put(("PRICE_UPDATE", {'isin': isin, 'price': price}))
        except Exception as e:
            self._log(f"Błąd podczas parsowania danych rynkowych: {e}")

    # ... (pozostałe metody BossaAPIClient bez zmian)
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
        if response and '<MktDataFull>' in response:
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
                if '<MktDataInc' in message:
                    self._parse_market_data(message)
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
            self.sync_port= int(self.sync_port)
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
        header_data = sock.recv(4)
        if not header_data: return None
        message_length = struct.unpack('<I', header_data)[0]
        if message_length == 0: return ""
        message_data = b''
        while len(message_data) < message_length:
            chunk = sock.recv(message_length - len(message_data))
            if not chunk: raise ConnectionError("Przerwano połączenie.")
            message_data += chunk
        return message_data.decode('utf-8').strip().rstrip('\x00')

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