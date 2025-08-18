import tkinter as tk
from tkinter import scrolledtext
import threading
import queue
import socket
import struct
import winreg
import xml.etree.ElementTree as ET
import time

class BossaApp:
    """Główna klasa aplikacji GUI, która zarządza interfejsem i klientem API."""
    def __init__(self, root):
        self.root = root
        self.root.title("BossaAPI Klient")
        self.root.geometry("800x750")

        self.client = None
        self.queue = queue.Queue()

        self.create_widgets()
        self.process_queue()

    def create_widgets(self):
        # --- Główny kontener ---
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # --- Ramka logowania ---
        login_frame = tk.Frame(main_frame)
        login_frame.pack(fill='x', pady=(0, 10))
        # ... (reszta kontrolek logowania bez zmian)

        # --- Ramka zarządzania filtrem ---
        filter_frame = tk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(filter_frame, text="ISIN:").pack(side='left', padx=(0, 5))
        self.isin_entry = tk.Entry(filter_frame, width=25)
        self.isin_entry.pack(side='left', padx=5)
        self.isin_entry.insert(0, "PL0GF0031252")

        self.add_filter_button = tk.Button(filter_frame, text="Dodaj do filtra", command=self.add_to_filter, state='disabled')
        self.add_filter_button.pack(side='left', padx=5)

        self.clear_filter_button = tk.Button(filter_frame, text="Wyczyść filtr", command=self.clear_filter, state='disabled')
        self.clear_filter_button.pack(side='left', padx=5)

        # --- Podział okna na logi i portfel ---
        paned_window = tk.PanedWindow(main_frame, orient='vertical', sashrelief='raised')
        paned_window.pack(fill='both', expand=True)

        # --- Górny panel: logi i komunikaty async ---
        top_panel = tk.Frame(paned_window)
        tk.Label(top_panel, text="Log statusu:").pack(anchor='w')
        self.status_log = scrolledtext.ScrolledText(top_panel, height=8, state='disabled')
        self.status_log.pack(fill='x', expand=True, pady=(0, 5))
        
        tk.Label(top_panel, text="Surowe komunikaty (kanał asynchroniczny):").pack(anchor='w')
        self.async_messages = scrolledtext.ScrolledText(top_panel, height=12, state='disabled', bg='lightgrey')
        self.async_messages.pack(fill='x', expand=True)
        paned_window.add(top_panel)
        
        # --- Dolny panel: portfel ---
        bottom_panel = tk.Frame(paned_window)
        tk.Label(bottom_panel, text="Dane portfela:").pack(anchor='w')
        self.portfolio_display = scrolledtext.ScrolledText(bottom_panel, height=10, state='disabled')
        self.portfolio_display.pack(fill='both', expand=True)
        paned_window.add(bottom_panel)

        # Dodanie pozostałych kontrolek logowania
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

    def log_message(self, widget, message):
        """Dodaje wiadomość do wybranego okna tekstowego."""
        widget.config(state='normal')
        widget.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        widget.yview(tk.END)
        widget.config(state='disabled')

    def start_login_thread(self):
        # ... (bez zmian)
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

    def process_queue(self):
        try:
            message_type, data = self.queue.get_nowait()
            if message_type == "LOG":
                self.log_message(self.status_log, data)
            elif message_type == "LOGIN_SUCCESS":
                self.log_message(self.status_log, "Logowanie udane! Możesz zarządzać filtrem.")
                self.disconnect_button.config(state='normal')
                self.add_filter_button.config(state='normal')
                self.clear_filter_button.config(state='normal')
            elif message_type == "ASYNC_MSG":
                self.log_message(self.async_messages, data.strip())
            elif message_type == "PORTFOLIO":
                self.log_message(self.status_log, "Otrzymano dane portfela.")
                self.display_portfolio(data)
            elif message_type == "DISCONNECTED":
                self.log_message(self.status_log, "Rozłączono.")
                self.login_button.config(state='normal')
                self.disconnect_button.config(state='disabled')
                self.add_filter_button.config(state='disabled')
                self.clear_filter_button.config(state='disabled')
                self.client = None
            elif message_type == "LOGIN_FAIL":
                self.log_message(self.status_log, f"Logowanie nie powiodło się: {data}")
                self.login_button.config(state='normal')

        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

    def add_to_filter(self):
        isin = self.isin_entry.get()
        if self.client and isin:
            self.log_message(self.status_log, f"Wysyłanie żądania dodania {isin} do filtra...")
            threading.Thread(target=self.client.add_to_filter, args=(isin,), daemon=True).start()

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
# KLASA BossaAPIClient - ZAKTUALIZOWANA O OBSŁUGĘ FILTRA
# -----------------------------------------------------------------------------

class BossaAPIClient:
    def __init__(self, username, password, gui_queue):
        # ... (atrybuty bez zmian)
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
        self.request_id = 100
        self.sync_lock = threading.Lock() # Zabezpieczenie dostępu do socketu synchronicznego

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

    def _send_and_receive_sync_orig(self, message):
        """Wysyła i odbiera wiadomość na sockecie synchronicznym w sposób bezpieczny wątkowo."""
        with self.sync_lock:
            try:
                if not self.sync_socket:
                    self.sync_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sync_socket.connect(('127.0.0.1', self.sync_port))
                
                self._send_message(self.sync_socket, message)
                response = self._receive_message(self.sync_socket)
                return response
            except Exception as e:
                self._log(f"BŁĄD komunikacji synchronicznej: {e}")
                # Resetowanie socketu w razie błędu
                if self.sync_socket:
                    self.sync_socket.close()
                self.sync_socket = None
                return None

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
        if response and '<MktDataFull>' in response: # Odpowiedź synchroniczna to MarketDataSnapshotFullRefresh [cite: 217]
            self._log(f"Pomyślnie dodano {isin} do filtra.")
        else:
            self._log(f"Błąd podczas dodawania do filtra. Odpowiedź: {response}")

    def clear_filter(self):
        """Wysyła żądanie wyczyszczenia filtra."""
        self.request_id += 1
        # Atrybut SubReqTyp="2" do czyszczenia filtra [cite: 207]
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
            if self.async_socket: self.async_socket.close()
            
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
                self.gui_queue.put(("LOGIN_SUCCESS",f"User already logged in."))
                self.is_logged_in = True
                self._async_listener()
            else:
                status = user_rsp.get('UserStat') if user_rsp is not None else 'brak'
                self.gui_queue.put(("LOGIN_FAIL", f"Status: {status}"))
        else:
            self.gui_queue.put(("LOGIN_FAIL", f"Nieoczekiwana odpowiedź: {response}"))
            if self.sync_socket: self.sync_socket.close()
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

    # Pozostałe metody (_get_ports_from_registry, _send_message, _receive_message, _parse_portfolio)
    # pozostają bez większych zmian, więc je pomijam dla zwięzłości, ale muszą być w kodzie.
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