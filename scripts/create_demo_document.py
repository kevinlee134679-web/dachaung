"""Create one clearly fictional PDF for the S02 manual-upload demonstration."""
import argparse
from pathlib import Path


def build():
    content=b'BT /F1 18 Tf 60 740 Td (FICTIONAL DEMO DOCUMENT) Tj 0 -40 Td /F1 12 Tf (No real patient, prescription, or clinical instruction.) Tj ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
             b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
             b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
             b'<< /Length '+str(len(content)).encode()+b' >>\nstream\n'+content+b'\nendstream']
    result=b'%PDF-1.4\n';offsets=[]
    for i,obj in enumerate(objects,1):
        offsets.append(len(result));result+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    start=len(result);result+=b'xref\n0 6\n0000000000 65535 f \n'
    for offset in offsets:result+=f'{offset:010d} 00000 n \n'.encode()
    return result+f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('test-output/fictional-record.pdf'));args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as stream:stream.write(build())
    print('Fictional PDF created; existing files are never overwritten.')
