import tkinter as tk
from tkinter import messagebox
from functools import partial
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import os

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

        delete_button = tk.Button(self.root, text="刪除所選", command=self.delete_selected)
        delete_button.pack(pady=10)

        self.root.mainloop()

    def authenticate(self):
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        return creds

    def _on_mousewheel(self, event, canvas):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def load_files(self, parent_id=None, window=None, title="Google Drive 檔案管理器"):
        if window is None:
            window = self.root

        if window != self.root:
            window.geometry("600x500")

        scroll_container = tk.Frame(window)
        scroll_container.pack(fill='both', expand=True)

        canvas = tk.Canvas(scroll_container)
        scrollbar = tk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
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

        self.files = result.get('files', [])
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
        delete_button = tk.Button(self.root, text="刪除所選", command=self.delete_selected)
        delete_button.pack(pady=10)

if __name__ == '__main__':
    GoogleDriveDeleter()
