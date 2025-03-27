import threading
import queue
from blessed import Terminal
import unicodedata
import time
import scapy.all as scapy
import socket
class ColumnDisplay:
    def __init__(self, num_columns=4):
        self.term = Terminal()
        self.num_columns = num_columns
        self.columns = [[] for _ in range(num_columns)]
        self.running = True
        self.input_queue = queue.Queue()
        self.lock = threading.Lock()
        self.resize_flag = False
        self.last_redraw = 0
        self.force_redraw = True  

    def calculate_layout(self):
        width = self.term.width
        self.col_width = (width // self.num_columns) - 1
        self.divider_positions = [i * (width // self.num_columns) 
                                for i in range(1, self.num_columns)]

    def wc_length(self, text):
        return sum(1 + (unicodedata.east_asian_width(c) in 'WF') 
                     for c in text)

    def trim_text(self, text):
        max_len = self.col_width - 3
        current_len = 0
        result = []
        for c in text:
            char_width = 1 + (unicodedata.east_asian_width(c) in 'WF')
            if current_len + char_width > max_len:
                break
            result.append(c)
            current_len += char_width
        return ''.join(result) + '...' if text != ''.join(result) else text

    def redraw_screen(self):
        now = time.monotonic()
        if not self.force_redraw and (now - self.last_redraw < 0.1):
            return
            
        with self.lock:
            print(self.term.clear, end='', flush=True)
            
            self.calculate_layout()
            
            for x in self.divider_positions:
                for y in range(self.term.height):
                    with self.term.location(x, y):
                        print('│', end='', flush=True)
            
            for col in range(self.num_columns):
                for row, text in enumerate(self.columns[col]):
                    x = col * (self.term.width // self.num_columns) + 1
                    trimmed = self.trim_text(text)
                    with self.term.location(x, row):
                        print(trimmed, end='', flush=True)
            
            self.last_redraw = now
            self.force_redraw = False

    def get_hostname(self, ip):
        try:
            return socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror):
            return "Unknown"
        
    def measure_ping(self, ip, count=3):
        """Измерение среднего ping до устройства (в мс)"""
        total_time = 0
        success = 0
        
        for _ in range(count):
            start_time = time.time()
            packet = scapy.IP(dst=ip)/scapy.ICMP()
            response = scapy.sr1(packet, timeout=1, verbose=False)
            
            if response:
                ping_time = (time.time() - start_time) * 1000  # мс
                total_time += ping_time
                success += 1
        
        return round(total_time / success, 2) if success else None
    def scan_thread(self):
        while self.running:
            self.input_queue.put((0,"---IP---".center(self.col_width-3)))
            self.input_queue.put((1,"---MAC---".center(self.col_width-3)))
            self.input_queue.put((2,"---HOSTNAME---".center(self.col_width-3)))
            self.input_queue.put((3,"---PING---".center(self.col_width-3)))
            request = scapy.ARP() 
            for i in range(0,2):
                request.pdst = f'192.168.{i}.0/24'
                broadcast = scapy.Ether() 
                broadcast.dst = 'ff:ff:ff:ff:ff:ff'
                request_broadcast = broadcast / request 
                clients = scapy.srp(request_broadcast, timeout=1, verbose=False)[0] 
        
                for element in clients: 
                    ip = element[1].psrc
                    mac = element[1].hwsrc
                    hostname = self.get_hostname(ip)
                    ping = self.measure_ping(ip)
                    if ip != None and mac != None and hostname != None and ping != None:
                        self.input_queue.put((0,ip))
                        self.input_queue.put((1,mac))
                        self.input_queue.put((2,hostname))
                        self.input_queue.put((3,f"{int(ping)} мс 📶"))
            
            time.sleep(60)
            #self.redraw_screen()
            for col in range(self.num_columns):
                self.columns[col].clear()

    def display_thread(self):
        self.redraw_screen()
        while self.running:
            try:
                if self.resize_flag:
                    self.force_redraw = True
                    self.resize_flag = False
                
                items = []
                while not self.input_queue.empty():
                    items.append(self.input_queue.get())
                
                if items:
                    with self.lock:
                        for item in items:
                            if item[0] == 'exit':
                                self.running = False
                                return
                            col, text = item
                            if 0 <= col < self.num_columns:
                                self.columns[col].append(text)
                                if len(self.columns[col]) > self.term.height - 2:
                                    self.columns[col].pop(0)
                        self.force_redraw = True
                
                if self.force_redraw:
                    self.redraw_screen()
                time.sleep(0.01)

            except Exception as e:
                print(f"Display error: {e}")
                self.running = False

    def input_thread(self):
        input_buffer = []
        prompt = "Ввод (формат: [1-4] текст): "
        with self.term.cbreak(), self.term.hidden_cursor():
            print(self.term.move(self.term.height, 1)) 
            while self.running:
                try:
                    print(f"\033[{self.term.height};1H{self.term.clear_eol}"
                          f"{prompt}{''.join(input_buffer)}_", 
                          end='', flush=True)
                    
                    inp = self.term.inkey(timeout=0.1)
                    if not inp:
                        continue
                    
                    if inp.code == self.term.KEY_ENTER:
                        if input_buffer:
                            self.process_input(''.join(input_buffer))
                            input_buffer = []
                    elif inp.code == self.term.KEY_BACKSPACE:
                        if input_buffer:
                            input_buffer.pop()
                    elif inp.code == self.term.KEY_RESIZE:
                        self.resize_flag = True
                        self.force_redraw = True
                    else:
                        input_buffer.append(inp)

                except KeyboardInterrupt:
                    self.running = False
                except Exception as e:
                    print(f"Input error: {e}")
                    self.running = False

    def process_input(self, cmd):
        if cmd.lower() in ('exit', 'q'):
            self.running = False
            return
        try:
            parts = cmd.split(maxsplit=1)
            if len(parts) == 2:
                col = int(parts[0])-1
                text = parts[1]
                if 0 <= col < self.num_columns:
                    self.input_queue.put((col, text))
        except ValueError:
            pass

    def run(self):
        print(self.term.clear, end='', flush=True) 
        display = threading.Thread(target=self.display_thread)
        inp = threading.Thread(target=self.input_thread)
        self.scan = threading.Thread(target=self.scan_thread)

        display.start()
        inp.start()
        self.scan.start()

        display.join()
        inp.join()
        self.scan.join()
        print(self.term.clear + "Программа завершена")

if __name__ == "__main__":
    import locale
    locale.setlocale(locale.LC_ALL, '')
    
    app = ColumnDisplay()
    app.run()