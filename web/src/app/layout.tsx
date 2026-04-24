import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Kế Toán Thuế AI - Trợ lý AI cho doanh nghiệp Việt Nam',
  description: 'Giải pháp kế toán thuế thông minh sử dụng AI. Tư vấn thuế, xử lý hóa đơn, đảm bảo tuân thủ quy định.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}