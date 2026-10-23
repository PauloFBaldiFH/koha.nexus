# Hướng dẫn sử dụng Koha.Nexus

Chín chương này hướng dẫn trình cài và bảng điều khiển Koha.Nexus, không thay tài liệu đầy đủ về biên mục và lưu thông của Koha. Nội dung được viết thủ công từ nguồn tiếng Bồ Đào Nha và tiếng Anh, đối chiếu mã 2a78bfa. Đọc mã không phải thử cài đặt thực tế. Tên hành động giữ tiếng Anh để khớp mã; giao diện có thể hiển thị bản dịch. Không dịch lệnh và đường dẫn. Đọc xác nhận trước khi thay hay xóa dữ liệu; không dựa vào số menu cũ.

## Mục lục

1. [Cài đặt](01-installation.md).
2. [Bắt đầu và sử dụng bảng điều khiển](02-panel.md).
3. [Backup và restore](03-backup-restore.md).
4. [Nhập dữ liệu thông minh](04-magic-import.md).
5. [Bổ sung dữ liệu và Z39.50/SRU](05-enrichment.md).
6. [Giao diện OPAC và staff](06-appearance.md).
7. [AI cục bộ](07-local-ai.md).
8. [Quản trị, thông báo và VPN](08-administration.md).
9. [Khắc phục sự cố và nhật ký](09-troubleshooting-logs.md).

[English](../en/README.md) · [Português brasileiro](../pt-BR/README.md) · [हिन्दी](../hi/README.md) · [বাংলা](../bn/README.md) · [Tiếng Việt](../vi/README.md) · [中文（简体）](../zh/README.md) · [日本語](../ja/README.md)

## Cần xác nhận

- Khả dụng công khai và URL Microsoft Store.
- RAM tối thiểu chính thức của Linux, chưa được kiểm tra đầu vào ép buộc theo số.
- Hoạt động MSIX đầy đủ trên ARM64; manifest là x64.
- Bố cục và phiên bản xuất riêng chưa có mẫu cùng kiểm tra kết quả.
- Khả dụng và điều kiện của nguồn ngoài từ mạng cục bộ.
- RAM, đĩa và thời gian phản hồi AI theo phần cứng và lựa chọn.
- Domain, mạng và chính sách cơ quan khi công khai dịch vụ.
- Nguyên nhân lỗi cụ thể khi thiếu toàn bộ thông báo và nhật ký.
