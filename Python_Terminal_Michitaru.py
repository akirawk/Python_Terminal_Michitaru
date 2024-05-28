# -*- coding: utf-8 -*-

import serial
import serial.tools.list_ports
import threading
import datetime
import os
import time

def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]

def select_serial_port():
    available_ports = list_serial_ports()
    if not available_ports:
        print("No serial ports available.")
        return None

    print("Available serial ports:")
    for i, port in enumerate(available_ports):
        print(f"{i}: {port}")

    while True:
        try:
            port_index = int(input("Select the serial port index: "))
            if 0 <= port_index < len(available_ports):
                return available_ports[port_index]
            else:
                print("Invalid index. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def get_baud_rate():
    while True:
        try:
            baud_rate = int(input("Enter the baud rate: "))
            return baud_rate
        except ValueError:
            print("Invalid input. Please enter a number.")

def create_log_file(port):
    today = datetime.datetime.now().strftime("%Y%m%d")
    log_dir = os.path.join(os.getcwd(), "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = os.path.join(log_dir, f"{port.replace('/', '_')}_{today}.log")
    return log_file

log_buffer = []
buffer_lock = threading.Lock()

def log_data(log_file, data):
    timestamp = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}]"
    log_entry = f"{timestamp} {data}\n"
    with buffer_lock:
        log_buffer.append(log_entry)

def write_log_file(log_file):
    while True:
        time.sleep(0.5)  # 少しの間待機してから書き込み
        with buffer_lock:
            if log_buffer:
                try:
                    with open(log_file, 'a', encoding='utf-8') as f:
                        while log_buffer:
                            f.write(log_buffer.pop(0))
                except IOError as e:
                    print(f"File access error: {e}. Retrying...")

def read_from_serial(ser, log_file, line_buffer_lock, line_buffer):
    while True:
        if ser.in_waiting > 0:
            char = ser.read(1).decode('utf-8')
            with line_buffer_lock:
                line_buffer.append(char)
            print(char, end='', flush=True)
            if char == '\r':
                with line_buffer_lock:
                    log_data(log_file, ''.join(line_buffer).strip())
                    line_buffer.clear()

def write_to_serial(ser, log_file, line_buffer_lock, line_buffer):
    while True:
        user_input = input()
        ser.write(user_input.encode('utf-8'))
        ser.write('\r'.encode('utf-8'))
        with line_buffer_lock:
            line_buffer.extend(list(user_input))
            line_buffer.append('\r')
            log_data(log_file, ''.join(line_buffer).strip())
            line_buffer.clear()
        for char in user_input:
            print(char, end='', flush=True)
        print('\r', end='', flush=True)
        if user_input.lower() == 'exit':
            print("Exiting...")
            break

def main():
    selected_port = select_serial_port()
    if not selected_port:
        return

    baud_rate = get_baud_rate()
    log_file = create_log_file(selected_port)
    print(f"Logging to file: {log_file}")

    try:
        # シリアルポートの初期化
        ser = serial.Serial(selected_port, baud_rate, timeout=1)

        line_buffer = []
        line_buffer_lock = threading.Lock()

        # スレッドの設定
        read_thread = threading.Thread(target=read_from_serial, args=(ser, log_file, line_buffer_lock, line_buffer), daemon=True)
        write_thread = threading.Thread(target=write_to_serial, args=(ser, log_file, line_buffer_lock, line_buffer), daemon=True)
        log_thread = threading.Thread(target=write_log_file, args=(log_file,), daemon=True)

        # スレッドの開始
        read_thread.start()
        write_thread.start()
        log_thread.start()

        # write_threadの終了を待つ
        write_thread.join()

    except serial.SerialException as e:
        print(f"Serial exception: {e}")
    except KeyboardInterrupt:
        print("Program terminated by user")
    finally:
        # シリアルポートを閉じる
        if ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
