import socket
import sys
import threading

ALLOW = {h.strip() for h in sys.argv[1].split(',')} if len(sys.argv) > 1 else {'api.anthropic.com'}
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 3128


def pump(a, b):
    try:
        while True:
            data = a.recv(65536)
            if not data:
                break
            b.sendall(data)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def handle(client):
    try:
        head = b''
        while b'\r\n\r\n' not in head:
            chunk = client.recv(4096)
            if not chunk:
                return
            head += chunk
        line = head.split(b'\r\n', 1)[0].decode(errors='replace')
        method, target = line.split(' ')[:2]
        host, _, port = target.partition(':')
        if method != 'CONNECT' or host not in ALLOW:
            client.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n')
            print(f'refused {method} {target}', flush=True)
            return
        upstream = socket.create_connection((host, int(port or 443)), timeout=30)
        upstream.settimeout(None)
        client.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        print(f'connect {host}', flush=True)
        threading.Thread(target=pump, args=(upstream, client), daemon=True).start()
        pump(client, upstream)
    except Exception as e:
        print(f'error {e}', flush=True)
    finally:
        client.close()


def main():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', PORT))
    srv.listen(64)
    print(f'egress proxy on {PORT}, allow {sorted(ALLOW)}', flush=True)
    while True:
        c, _ = srv.accept()
        threading.Thread(target=handle, args=(c,), daemon=True).start()


if __name__ == '__main__':
    main()
