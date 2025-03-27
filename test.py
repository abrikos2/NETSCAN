import scapy.all as scapy
import socket

def get_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror):
        return "Unknown"

request = scapy.ARP() 
for i in range(0,5):
    request.pdst = f'192.168.{i}.0/24'
    broadcast = scapy.Ether() 
    
    broadcast.dst = 'ff:ff:ff:ff:ff:ff'
    
    request_broadcast = broadcast / request 
    clients = scapy.srp(request_broadcast, timeout=1, verbose=False)[0] 
    
    print(f"\nScanning 192.168.{i}.0/24:")
    print("IP Address\t\tMAC Address\t\tHostname")
    print("--------------------------------------------------")
    
    for element in clients: 
        ip = element[1].psrc
        mac = element[1].hwsrc
        hostname = get_hostname(ip)
        print(f"{ip}\t\t{mac}\t\t{hostname}")