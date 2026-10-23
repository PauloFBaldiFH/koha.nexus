# 3. Backup và restore

[Mục lục](README.md)

## Các tác vụ khác nhau

Nhấn b mở **Backup center**. **Download latest backup** lấy tệp đã có; **Generate manual backup and download to PC** tạo bản cơ sở dữ liệu mới; **Export MARC21 records now** xuất biểu ghi thư mục và biểu ghi chuẩn; **Restore database** thay cơ sở dữ liệu; **Configure cloud backup** cấu hình gửi ngoài; **Test integrity of latest backup** thử trong cơ sở dữ liệu tạm. restore là thẻ trong trung tâm này, không phải nút phía trên hay mục riêng trên màn hình chính.

SQL backup không phải ảnh toàn bộ Windows hoặc Debian. Gói MARC `.tar.gz` không thay SQL để phục hồi bạn đọc và lưu thông. SQL tự động và bản an toàn mặc định ở `/var/backups/koha_sql`; MARC ở `/var/backups/koha_marc`. Backup thủ công chọn đích riêng, mặc định thư mục `backups` thuộc thư mục nhà mà bảng điều khiển nhận diện.

Tệp lớn ghi vào `.part`, kiểm tra xong mới đổi sang tên cuối. Không chọn `.part` làm bản hoàn chỉnh. Chọn gz, zst hoặc xz trong **Compression** sẽ tự lưu, chỉ áp dụng cho bản mới, không nén lại bản cũ. Thiếu chương trình cần thiết có thể dẫn đến thông báo và dùng gzip. restore đọc `.sql`, `.sql.gz`, `.sql.zst`, `.sql.xz` được hỗ trợ bất kể lựa chọn nén hiện tại; đuôi tệp không chứng minh nội dung hợp lệ.

## Tạo, chuyển và thử

Mở thẻ tạo thủ công, kiểm tra thư mục máy chủ rồi **Save backup**. Đợi tạo và kiểm tra; màn hình không đóng trong lúc lưu hoặc sao chép. Ghi tên, dung lượng và đường dẫn. WSL có **Save to Windows Downloads** hoặc **Choose folder in Windows**; máy chủ từ xa cung cấp lệnh chuyển để chạy trên máy tính của bạn. Xác minh tệp tới nơi rồi **Finish and exit**. Không chép lệnh minh họa của máy khác.

Nếu khóa chung báo backup hay restore đang chạy, hãy đợi, đừng chạy cạnh tranh bên ngoài. Tải bản mới nhất không tạo bản mới. Cần bản ngay trước một thay đổi thì tạo thủ công.

Trong thẻ kiểm tra, xem ngày và tệp, có thể **Choose another file**, rồi xác nhận. Công cụ nhập vào cơ sở dữ liệu tạm, báo bảng, biểu ghi và bạn đọc; không thay bản đang dùng. Thành công chỉ nói về đúng tệp được thử trong môi trường đó. MARC xuất khi Koha vẫn chạy; kiểm tra nội dung, đường dẫn, chuyển tệp và kết quả gửi đám mây riêng.

## Đám mây và lịch

Có hai tuyến nhanh Google Drive và các dịch vụ OneDrive, MEGA, S3. Chọn theo nơi ủy quyền: trên máy chủ hay máy khác. Theo địa chỉ hiện trên hệ thống của mình. S3 cần đúng dịch vụ, vùng, endpoint và bucket. Đọc kết quả tải lên thực tế, sửa lỗi và xác minh bản đích trước khi tin cậy. Không đưa thông tin ủy quyền vào ảnh hay báo cáo công khai.

Mặc định SQL mỗi ngày 23:00, MARC Chủ nhật 03:00 theo giờ máy chủ. Cron đã tùy chỉnh có thể khác. Phải có máy và Linux đang chạy. Chỉ báo lần chạy đêm và tệp mới nhất cũng có thể thuộc hai lần khác nhau.

## restore thay thế dữ liệu

**Restore database thay cơ sở dữ liệu hiện tại.** Đặt lịch bảo trì và giữ bản ngoài máy trước khi bắt đầu; bảng điều khiển không tự hoàn tất khuyến nghị chuyển ngoài này. Chọn đúng bản, chuyển lên máy chủ theo hướng dẫn. WSL có thể chép tệp Windows sang vùng Linux trước.

Đọc kiểm tra khả năng đọc, nội dung, toàn vẹn và dung lượng. Điều tra tệp đáng ngờ. Có thể rút lui trước xác nhận thay thế cuối; sau đó không hủy trong bảng điều khiển.

Trước tiên công cụ nhập thử và kiểm tra bảng thiết yếu. Nếu cơ sở hiện tại có bảng, nó tạo và kiểm chứng bản `pre_restore_safety_backup_`; lỗi ở đây phải dừng trước thay thế. Cơ sở trống có thể bỏ qua. Sau đó dừng máy khách, tạo lại và nhập cơ sở, nâng cấu trúc, đồng bộ tìm kiếm, dựng chỉ mục, khởi động dịch vụ và thử áp dụng lại giao diện đã lưu.

Phân biệt lỗi trước thay thế với lỗi nhập, nâng cấu trúc hay chỉ mục. Có trường hợp thử rollback nhưng rollback cũng có thể hỏng. Lỗi chỉ mục có thể xuất hiện sau khi cơ sở đã thay, không chứng minh dữ liệu cũ đã trở lại.

Đọc `/var/log/koha-easy-install/restore.log`, `/var/log/koha-easy-install/restore-import.log`, `/var/log/koha-easy-install/zebra-rebuild.log`. Sau cùng thử staff, OPAC, dữ liệu và tìm kiếm. SQL không bảo đảm phục hồi tệp ngoài cơ sở. Khi trạng thái chưa rõ, đừng lặp lại toàn bộ thao tác một cách tự động.

## Nguồn đã kiểm tra

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
