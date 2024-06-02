# -*- coding: utf-8 -*-

import serial
import serial.tools.list_ports
import threading
import datetime
import os
import time
import requests
from dateutil import parser

# 時計送信機能
TimerIntervalSender = True

# グローバル停止フラグ
stop_flag = threading.Event()

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
    log_file_path = os.path.join(log_dir, f"{port.replace('/', '_')}_{today}.log")
    return log_file_path

def log_data(log_file, data):
    timestamp = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}]"
    log_entry = f"{timestamp} {data}\n"
    log_file.write(log_entry)
    log_file.flush()

def read_from_serial(ser, log_file, line_buffer_lock, line_buffer):
    while not stop_flag.is_set():
        try:
            if ser.in_waiting > 0:
                char = ser.read(1).decode('utf-8', errors='ignore')
                with line_buffer_lock:
                    line_buffer.append(char)
                print(char, end='', flush=True)
                if char == '\r':
                    with line_buffer_lock:
                        log_data(log_file, ''.join(line_buffer).strip())
                        line_buffer.clear()
            else:
                time.sleep(0.1)
        except serial.SerialException as e:
            if not stop_flag.is_set():
                print(f"Serial exception in read thread: {e}")

def write_to_serial(ser, log_file, line_buffer_lock, line_buffer):
    while not stop_flag.is_set():
        try:
            user_input = input()
            for char in user_input:
                ser.write(char.encode('utf-8'))
                with line_buffer_lock:
                    line_buffer.append(char)
                print(char, end='', flush=True)
            ser.write('\r'.encode('utf-8'))
            with line_buffer_lock:
                line_buffer.append('\r')
                log_data(log_file, ''.join(line_buffer).strip())
                line_buffer.clear()
            print('\r', end='', flush=True)
            if user_input.lower() == 'exit':
                print("Exiting...")
                stop_flag.set()
                break
        except EOFError:
            stop_flag.set()
            break

def get_formatted_time(max_response_time=0.5):
    try:
        start_time = time.time()
        response = requests.get("https://worldtimeapi.org/api/timezone/Asia/Tokyo/")
        response_time = time.time() - start_time
        if response_time > max_response_time:
            print(f"Response time {response_time}s exceeded the maximum allowed {max_response_time}s. Discarding response.")
            return None
        data = response.json()
        dt = parser.isoparse(data['datetime'])
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return formatted_time
    except (requests.RequestException, ValueError) as e:
        print(f"Failed to get time: {e}")
        return None

def print_and_send_time_periodically(ser, log_file):
    while not stop_flag.is_set():
        try:
            start_time = time.perf_counter()
            formatted_time = get_formatted_time()
            if formatted_time:
                print(formatted_time)
                ser.write((formatted_time + '\r').encode('utf-8'))
                log_data(log_file, formatted_time)
            else:
                print("Skipping time announcement.")
            while not stop_flag.is_set():
                current_time = time.perf_counter()
                elapsed_time = current_time - start_time
                if elapsed_time >= 600:
                    break
                time.sleep(1)

        except Exception as e:
            if not stop_flag.is_set():
                print(f"Exception in time thread: {e}")

def main():
    global log_file
    
    print("Python_Terminal(Zihou Ver) Ver.1.0.2")

    selected_port = select_serial_port()
    if not selected_port:
        return

    baud_rate = get_baud_rate()
    log_file_path = create_log_file(selected_port)
    print(f"Logging to file: {log_file_path}")

    try:
        # シリアルポートの初期化
        ser = serial.Serial(selected_port, baud_rate, timeout=1)

        line_buffer = []
        line_buffer_lock = threading.Lock()

        # ログファイルのオープン
        with open(log_file_path, 'a', encoding='utf-8') as log_file:
            # スレッドの設定
            read_thread = threading.Thread(target=read_from_serial, args=(ser, log_file, line_buffer_lock, line_buffer), daemon=True)
            write_thread = threading.Thread(target=write_to_serial, args=(ser, log_file, line_buffer_lock, line_buffer), daemon=True)

            if TimerIntervalSender:
                time_thread = threading.Thread(target=print_and_send_time_periodically, args=(ser, log_file), daemon=True)

            # スレッドの開始
            read_thread.start()
            write_thread.start()

            if TimerIntervalSender:
                time_thread.start()

            # write_threadの終了を待つ
            write_thread.join()

    except serial.SerialException as e:
        print(f"Serial exception: {e}")
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
        stop_flag.set()
    finally:
        stop_flag.set()
        read_thread.join()
        write_thread.join()

        if TimerIntervalSender:
            time_thread.join()

        # シリアルポートを閉じる
        if ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
