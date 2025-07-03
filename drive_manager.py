import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
from functools import partial
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload
import mimetypes
import threading
import sys
import os

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

SCOPES = ['https://www.googleapis.com/auth/drive']

class GoogleDriveDeleter:
    def __init__(self):
        self.creds = self.authenticate()
        self.service = build('drive', 'v3', credentials=self.creds)
        self.files = []
        self.check_vars = []
        self.file_ids = []

        self.root = tk.Tk()
        self.root.title("Google Drive 檔案管理器")
        self.root.geometry("600x500")

        self.load_files()

        self.root.mainloop()

    def authenticate(self):
        from cryptography.fernet import Fernet
        import json

        if os.path.exists(resource_path('token.enc')):
            key = b'MKfuZvgSDTEniCDEHKb7Py1HFWiJFMTzGWWTkWaXgWs='
            fernet = Fernet(key)

            with open(resource_path('token.enc'), 'rb') as f:
                encrypted = f.read()
                decrypted = fernet.decrypt(encrypted)
                token_info = json.loads(decrypted.decode())

                creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(resource_path('credentials.json'), SCOPES)
            creds = flow.run_local_server(port=0)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

            print("\n⚠️ 請執行 encrypt_token.py 將 token.json 加密後再重新執行本程式")
            sys.exit(0)

        return creds

    def _on_mousewheel(self, event, canvas):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def load_files(self, parent_id=None, window=None, title="Google Drive 檔案管理器", keyword=None):

        if window is None:
            window = self.root

        if window != self.root:
            window.geometry("600x500")

        self.current_window = window
        self.current_parent_id = parent_id

        for widget in window.winfo_children():
            widget.destroy()

        if window == self.root:
            search_frame = tk.Frame(window)
            search_frame.pack(pady=5)

            upload_frame = tk.Frame(window)
            upload_frame.pack(pady=5)

            self.search_var = tk.StringVar()
            search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=40)
            search_entry.pack(side='left', padx=(0, 5))

            search_button = tk.Button(search_frame, text="搜尋/刷新", command=self.search_files)
            search_button.pack(side='left')

            upload_btn = tk.Button(upload_frame, text="+ 上傳檔案", command=self.upload_files)
            upload_btn.pack(side='left', padx=(0, 5))

            folder_btn = tk.Button(upload_frame, text="+ 上傳資料夾", command=self.upload_folder)
            folder_btn.pack(side='left')

        scroll_container = tk.Frame(window)
        scroll_container.pack(fill='both', expand=True)

        canvas = tk.Canvas(scroll_container)
        scrollbar = tk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: self._on_mousewheel(ev, canvas)))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        query = f"'{parent_id}' in parents" if parent_id else "'root' in parents"
        result = self.service.files().list(
            q=query,
            fields="files(id, name, mimeType)",
            pageSize=100
        ).execute()

        all_files = result.get('files', [])

        if keyword:
            keyword_lower = keyword.lower()
            self.files = [f for f in all_files if keyword_lower in f['name'].lower()]
        else:
            self.files = all_files

        self.check_vars = []
        self.file_ids = []

        for file in self.files:
            var = tk.BooleanVar()
            self.check_vars.append(var)
            self.file_ids.append(file['id'])

            frame = tk.Frame(scrollable_frame)
            frame.pack(anchor='w', padx=10, pady=2)

            cb = tk.Checkbutton(frame, variable=var)
            cb.pack(side='left')

            is_folder = file['mimeType'] == 'application/vnd.google-apps.folder'
            display_name = f"📁 {file['name']}" if is_folder else file['name']
            label = tk.Label(frame, text=display_name, width=40, anchor='w')
            label.pack(side='left')

            if is_folder:
                open_btn = tk.Button(
                    frame,
                    text="開啟資料夾",
                    command=partial(self.open_folder, file['id'], file['name'])
                )
                open_btn.pack(side='left', padx=(10, 0))

            del_btn = tk.Button(
                frame,
                text="刪除",
                command=partial(self.delete_file, file['id'], file['name'])
            )
            del_btn.pack(side='left', padx=(10, 0))

            if not is_folder:
                download_btn = tk.Button(
                    frame,
                    text="下載",
                    command=partial(self.download_file, file['id'], file['name'])
                )
                download_btn.pack(side='left', padx=(10, 0))
        if window == self.root:
            delete_button = tk.Button(window, text="刪除所選", command=self.delete_selected)
            delete_button.pack(pady=10)

    def open_folder(self, folder_id, folder_name):
        new_window = tk.Toplevel(self.root)
        new_window.title(folder_name)
        self.load_files(parent_id=folder_id, window=new_window, title=folder_name)

    def delete_file(self, file_id, name):
        try:
            self.service.files().delete(fileId=file_id).execute()
            messagebox.showinfo("成功", f"檔案「{name}」已刪除")
            self.refresh_main()
        except Exception as e:
            messagebox.showerror("錯誤", f"無法刪除檔案：{e}")

    def delete_selected(self):
        for i, var in enumerate(self.check_vars):
            if var.get():
                file_id = self.file_ids[i]
                try:
                    self.service.files().delete(fileId=file_id).execute()
                except Exception as e:
                    messagebox.showerror("錯誤", f"刪除失敗：{e}")
        messagebox.showinfo("完成", "所選檔案已刪除")
        self.refresh_main()

    def refresh_main(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.load_files()

    def search_files(self):
        keyword = self.search_var.get().strip()
        self.load_files(parent_id=self.current_parent_id, window=self.current_window, keyword=keyword)
    
    def download_file(self, file_id, name):
        threading.Thread(target=self._download_file_worker, args=(file_id, name)).start()
        
    def _download_file_worker(self, file_id, name):
        try:
            file_path = filedialog.asksaveasfilename(title="下載檔案另存為", initialfile=name)
            if not file_path:
                return

            request = self.service.files().get_media(fileId=file_id)
            from googleapiclient.http import MediaIoBaseDownload
            import io

            fh = io.FileIO(file_path, mode='wb')
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            self.root.after(0, lambda: messagebox.showinfo("成功", f"檔案「{name}」已下載至：\n{file_path}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("錯誤", f"無法下載檔案：{e}"))
    
    def upload_files(self):
        file_paths = filedialog.askopenfilenames(title="選擇要上傳的檔案")
        if not file_paths:
            return
        threading.Thread(target=self._upload_files_worker, args=(file_paths,)).start()

    def _upload_files_worker(self, file_paths):
        for path in file_paths:
            filename = os.path.basename(path)
            mime_type, _ = mimetypes.guess_type(path)
            file_metadata = {
                'name': filename,
                'parents': [self.current_parent_id] if self.current_parent_id else []
            }

            media = MediaFileUpload(path, mimetype=mime_type, resumable=True)
            try:
                self.service.files().create(body=file_metadata, media_body=media).execute()
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("錯誤", f"檔案「{filename}」上傳失敗：{e}"))

        self.root.after(0, lambda: messagebox.showinfo("成功", "所有檔案已上傳！"))
        self.root.after(0, self.refresh_main)

    def upload_folder(self):
        folder_path = filedialog.askdirectory(title="選擇要上傳的資料夾")
        if not folder_path:
            return

        parent_id = self.current_parent_id or None
        self._upload_folder_recursive(folder_path, parent_id)
        messagebox.showinfo("完成", "資料夾上傳完成！")
        self.refresh_main()

    def _upload_folder_recursive(self, local_path, parent_drive_id):
        folder_name = os.path.basename(local_path)
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_drive_id] if parent_drive_id else []
        }

        folder = self.service.files().create(body=folder_metadata, fields='id').execute()
        new_folder_id = folder.get('id')

        entries = os.listdir(local_path)

        for entry in entries:
            entry_path = os.path.join(local_path, entry)
            if os.path.isdir(entry_path):
                self._upload_folder_recursive(entry_path, new_folder_id)
            else:
                mime_type, _ = mimetypes.guess_type(entry_path)
                file_metadata = {
                    'name': os.path.basename(entry_path),
                    'parents': [new_folder_id]
                }
                media = MediaFileUpload(entry_path, mimetype=mime_type, resumable=True)
                try:
                    self.service.files().create(body=file_metadata, media_body=media).execute()
                except Exception as e:
                    messagebox.showerror("錯誤", f"檔案「{entry_path}」上傳失敗：{e}")

if __name__ == '__main__':
    GoogleDriveDeleter()

# pyinstaller --windowed --onefile --add-data "credentials.json;." --add-data "token.enc;." drive_manager.py
