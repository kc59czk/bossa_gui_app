import os
from dotenv import load_dotenv
import socket
import struct
import threading
import xml.etree.ElementTree as ET
import winreg
#from lxml import etree

class BossaAPIClient:
    """
    Klient do obsługi bossaAPI w celu logowania i sprawdzania stanu portfela.
    Komunikuje się z lokalnie uruchomioną aplikacją bossaNOL3.
    """
    def __init__(self, username=None, password=None):
        load_dotenv()
        self.username = username if username is not None else os.getenv('USERNAME')
        self.password = password if password is not None else os.getenv('PASSWORD')
        self.sync_port = None
        self.async_port = None
        self.sync_socket = None
        self.async_socket = None
        self.is_logged_in = False
        self.portfolio = {}
        self.portfolio_received_event = threading.Event()
        self.listener_thread = None

    def _get_ports_from_registry(self):
        """Odczytuje porty synchroniczny i asynchroniczny z rejestru Windows."""
        try:
            key_path = r"Software\COMARCH S.A.\NOL3\7\Settings"
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            self.sync_port, _ = winreg.QueryValueEx(registry_key, "nca_psync")
            self.async_port, _ = winreg.QueryValueEx(registry_key, "nca_pasync")
            self.sync_port = int(self.sync_port)
            self.async_port = int(self.async_port)
            winreg.CloseKey(registry_key)
            print(f"Pomyślnie odczytano porty z rejestru: Sync={self.sync_port}, Async={self.async_port}")
            return True
        except FileNotFoundError:
            print("Błąd: Nie można znaleźć klucza rejestru bossaNOL3. Upewnij się, że aplikacja jest zainstalowana.")
            return False
        except Exception as e:
            print(f"Wystąpił nieoczekiwany błąd podczas odczytu rejestru: {e}")
            return False

    def _send_message(self, sock, message):
        """Wysyła wiadomość z 4-bajtowym nagłówkiem długości."""
        encoded_message = message.encode('utf-8')
        header = struct.pack('<I', len(encoded_message))
        sock.sendall(header)
        sock.sendall(encoded_message)

    def _receive_message(self, sock):
        """Odbiera wiadomość, najpierw odczytując 4-bajtowy nagłówek długości."""
        header_data = sock.recv(4)
        if not header_data:
            return None
        
        message_length = struct.unpack('<I', header_data)[0]
        message_data = b''
        while len(message_data) < message_length:
            chunk = sock.recv(message_length - len(message_data))
            if not chunk:
                raise ConnectionError("Połączenie zostało przerwane podczas odbierania danych.")
            message_data += chunk
            
        return message_data.decode('utf-8').strip().rstrip('\x00')

    def _async_listener(self):
        """Pętla działająca w osobnym wątku, nasłuchująca na porcie asynchronicznym."""
        try:
            self.async_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.async_socket.connect(('127.0.0.1', self.async_port))
            print("Połączono z portem asynchronicznym. Oczekiwanie на dane o portfelu...")

            while self.is_logged_in:
                message = self._receive_message(self.async_socket)
                if message is None:
                    break
                
                if '<Statement' in message:
                    print("Otrzymano komunikat o stanie portfela.")
                    self._parse_portfolio(message)
                    self.portfolio_received_event.set()

        except ConnectionAbortedError:
             print("Połączenie asynchroniczne zostało zamknięte.")
        except Exception as e:
            if self.is_logged_in:
                print(f"Błąd w wątku asynchronicznym: {e}")
        finally:
            if self.async_socket:
                self.async_socket.close()

    def _parse_portfolio(self, xml_data):
        """Paruje dane XML z wyciągiem i zapisuje je w słowniku."""
        root = ET.fromstring(xml_data)
        for statement in root.findall('Statement'):
            account_id = statement.get('Acct')
            self.portfolio[account_id] = {'funds': {}, 'positions': []}
            
            for fund in statement.findall('Fund'):
                name = fund.get('name')
                value = fund.get('value')
                self.portfolio[account_id]['funds'][name] = value
            
            for position in statement.findall('.//Position'):
                instrument = position.find('Instrmt')
                pos_data = {
                    'symbol': instrument.get('Sym'),
                    'isin': instrument.get('ID'),
                    'quantity': position.get('Acc110'),
                    'blocked_quantity': position.get('Acc120')
                }
                self.portfolio[account_id]['positions'].append(pos_data)

    def connect_and_login(self):
        """Nawiązuje połączenie i wysyła żądanie logowania."""
        if not self._get_ports_from_registry():
            return False

        response = None
        try:
            self.sync_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sync_socket.connect(('127.0.0.1', self.sync_port))
            
            login_request = (
                f'<FIXML v="5.0" r="20080317" s="20080314">'
                f'<UserReq UserReqID="18" UserReqTyp="1" Username="{self.username}" Password="{self.password}"/>'
                f'</FIXML>'
            )
            
            print("Wysyłanie żądania logowania...")
            self._send_message(self.sync_socket, login_request)
            response = self._receive_message(self.sync_socket)
            print("\n--- DEBUG ---\n")
            print(f"Otrzymano odpowiedź: {type(response)}")
            print(f"Surowa odpowiedz z serwera: {response!r}")
            if response is not None:
                print("Odpowiedź serwera:", {len(response)})
            print("\n--- DEBUG END ---\n")
            if response and '<UserRsp' in response:
                root = ET.fromstring(response)
                user_rsp = root.find('UserRsp')
                if user_rsp is not None and user_rsp.get('UserStat') == '1':
                    print("Logowanie udane!")
                    self.is_logged_in = True
                    self.listener_thread = threading.Thread(target=self._async_listener)
                    self.listener_thread.start()
                    return True
                else:
                    status = user_rsp.get('UserStat') if user_rsp is not None else 'brak'
                    print(f"Logowanie nie powiodło się. Status: {status}")
                    return False
            else:
                print(f"Otrzymano nieoczekiwaną odpowiedź serwera: {response}")
                return False

        except Exception as e:
            print(f"Wystąpił błąd podczas logowania: {e}")

    def get_portfolio_state(self, timeout=15):
        """Czeka na otrzymanie danych o portfelu i je zwraca."""
        print(f"Oczekiwanie na dane o portfelu (maksymalnie {timeout} sekund)...")
        received = self.portfolio_received_event.wait(timeout)
        if received:
            return self.portfolio
        else:
            print("Nie otrzymano informacji o portfelu w wyznaczonym czasie.")
            return None

    def disconnect(self):
        """Wysyła komunikat wylogowania i zamyka połączenia."""
        self.is_logged_in = False
        print("Rozłączanie...")
        if self.sync_socket:
            try:
                logout_request = (
                    '<FIXML v="5.0" r="20080317" s="20080314">'
                    '<UserReq UserReqID="999" UserReqTyp="2" Username="BOS"/>'
                    '</FIXML>'
                )
                print(logout_request)
                self._send_message(self.sync_socket, logout_request)
            except Exception as e:
                print(f"Błąd podczas wysyłania komunikatu wylogowania: {e}")
            finally:
                self.sync_socket.close()
        
        if self.listener_thread and self.listener_thread.is_alive():
             self.listener_thread.join(timeout=2)