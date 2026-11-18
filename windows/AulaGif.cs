using System;
using System.IO;
using System.Drawing;
using System.Drawing.Imaging;
using System.Drawing.Drawing2D;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.ComponentModel;
using Microsoft.Win32.SafeHandles;
using System.Threading;
using System.Windows.Forms;

// F108 Pro only. Protocol references are in README.txt. No driver installation.
class AulaGif {
 const int W=240,H=135,FrameBytes=64800,MaxFrames=141;
 [StructLayout(LayoutKind.Sequential)] struct InterfaceData { public int size; public Guid guid; public int flags; public IntPtr reserved; }
 [StructLayout(LayoutKind.Sequential)] struct Attributes { public int size; public ushort vid,pid,version; }
 [StructLayout(LayoutKind.Sequential)] struct Caps {
  public ushort usage,page,input,output,feature;
  [MarshalAs(UnmanagedType.ByValArray,SizeConst=17)] public ushort[] reserved;
  [MarshalAs(UnmanagedType.ByValArray,SizeConst=10)] public ushort[] counts;
 }
 [StructLayout(LayoutKind.Sequential)] struct Overlapped { public IntPtr Internal,InternalHigh; public uint Offset,OffsetHigh; public IntPtr Event; }
 [DllImport("hid.dll")] static extern void HidD_GetHidGuid(out Guid g);
 [DllImport("hid.dll",SetLastError=true)] static extern bool HidD_GetAttributes(SafeFileHandle h,ref Attributes a);
 [DllImport("hid.dll",SetLastError=true)] static extern bool HidD_GetPreparsedData(SafeFileHandle h,out IntPtr p);
 [DllImport("hid.dll")] static extern bool HidD_FreePreparsedData(IntPtr p);
 [DllImport("hid.dll")] static extern int HidP_GetCaps(IntPtr p,out Caps c);
 [DllImport("hid.dll",SetLastError=true)] static extern bool HidD_SetFeature(SafeFileHandle h,byte[] b,int n);
 [DllImport("hid.dll",SetLastError=true)] static extern bool HidD_GetFeature(SafeFileHandle h,byte[] b,int n);
 [DllImport("setupapi.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr SetupDiGetClassDevs(ref Guid g,IntPtr en,IntPtr parent,uint flags);
 [DllImport("setupapi.dll",SetLastError=true)] static extern bool SetupDiEnumDeviceInterfaces(IntPtr set,IntPtr dev,ref Guid g,uint i,ref InterfaceData d);
 [DllImport("setupapi.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr set,ref InterfaceData d,IntPtr detail,uint size,out uint needed,IntPtr dev);
 [DllImport("setupapi.dll")] static extern bool SetupDiDestroyDeviceInfoList(IntPtr set);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern SafeFileHandle CreateFile(string path,uint access,uint share,IntPtr sa,uint creation,uint flags,IntPtr template);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool WriteFile(SafeFileHandle h,IntPtr b,uint n,out uint done,IntPtr ov);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool ReadFile(SafeFileHandle h,IntPtr b,uint n,out uint done,IntPtr ov);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetOverlappedResult(SafeFileHandle h,IntPtr ov,out uint done,bool wait);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool CancelIoEx(SafeFileHandle h,IntPtr ov);
 class Device { public string path; public Caps caps; }
 static Exception Win(string s) { int code=Marshal.GetLastWin32Error();return new Win32Exception(code,s+" (Win32 "+code+": "+new Win32Exception(code).Message+")"); }
 static List<Device> Devices() {
  var list=new List<Device>(); Guid guid; HidD_GetHidGuid(out guid);
  IntPtr set=SetupDiGetClassDevs(ref guid,IntPtr.Zero,IntPtr.Zero,18);
  if(set==new IntPtr(-1)) throw Win("USB enumeration");
  try { for(uint i=0;;i++) {
   var d=new InterfaceData(); d.size=Marshal.SizeOf(d);
   if(!SetupDiEnumDeviceInterfaces(set,IntPtr.Zero,ref guid,i,ref d)) { if(Marshal.GetLastWin32Error()==259) break; throw Win("USB enumeration"); }
   uint needed; SetupDiGetDeviceInterfaceDetail(set,ref d,IntPtr.Zero,0,out needed,IntPtr.Zero);
   IntPtr buf=Marshal.AllocHGlobal((int)needed);
   try { Marshal.WriteInt32(buf,IntPtr.Size==8?8:6);
    if(!SetupDiGetDeviceInterfaceDetail(set,ref d,buf,needed,out needed,IntPtr.Zero)) throw Win("USB path");
    string path=Marshal.PtrToStringUni(IntPtr.Add(buf,4));
    if(path.IndexOf("vid_0c45&pid_800a",StringComparison.OrdinalIgnoreCase)<0) continue;
    using(var h=CreateFile(path,0,3,IntPtr.Zero,3,0,IntPtr.Zero)) {
     if(h.IsInvalid) {Console.WriteLine("Cannot open "+path+": "+Win("Read keyboard identity").Message);continue;}
     var a=new Attributes(); a.size=Marshal.SizeOf(a);
     if(!HidD_GetAttributes(h,ref a) || a.vid!=0x0c45 || a.pid!=0x800a) continue;
     IntPtr p; if(!HidD_GetPreparsedData(h,out p)) throw Win("Read HID descriptor");
     try { Caps c; if(HidP_GetCaps(p,out c)!=0x110000) throw new Exception("Invalid HID capabilities"); list.Add(new Device {path=path,caps=c}); }
     finally {HidD_FreePreparsedData(p);}
    }
   } finally {Marshal.FreeHGlobal(buf);}
  }} finally {SetupDiDestroyDeviceInfoList(set);}
  return list;
 }
 static byte[] ConvertGif(string file,string folder) {
  Directory.CreateDirectory(folder);
  using(var src=Image.FromFile(file)) {
   int n=src.GetFrameCount(FrameDimension.Time),count=Math.Min(n,MaxFrames);
   if(n<1 || n>20000) throw new Exception("Unsupported frame count");
   byte[] delays=null; try {delays=src.GetPropertyItem(0x5100).Value;} catch(ArgumentException) {}
   int[] ms=new int[n]; for(int i=0;i<n;i++) {ms[i]=delays!=null && delays.Length>=4*(i+1)?BitConverter.ToInt32(delays,4*i)*10:100; if(ms[i]<=0) ms[i]=100;}
   var data=new byte[((256+count*FrameBytes+4095)/4096)*4096];
   for(int i=0;i<data.Length;i++) data[i]=255; data[0]=(byte)count;
   var manifest=new System.Text.StringBuilder("frame,source_frame,delay_ms\r\n");
   double accumulated=0; int emitted=0; long originalMs=0;
   for(int f=0;f<count;f++) {
    int first=f*n/count,last=(f+1)*n/count,duration=0;
    for(int j=first;j<last;j++) duration+=ms[j]; originalMs+=duration;
    accumulated+=duration/20.0;
    int ticks=Math.Max(1,(int)Math.Round(accumulated)-emitted);
    if(ticks>255) throw new Exception("Frame delay exceeds 5.1 seconds; shorten GIF holds first.");
    emitted+=ticks; data[f+1]=(byte)ticks;
    src.SelectActiveFrame(FrameDimension.Time,first);
    using(var bmp=new Bitmap(W,H,PixelFormat.Format24bppRgb)) {
     using(var g=Graphics.FromImage(bmp)) {
      g.Clear(Color.Black);g.InterpolationMode=InterpolationMode.HighQualityBicubic;g.PixelOffsetMode=PixelOffsetMode.HighQuality;
      double scale=Math.Min((double)W/src.Width,(double)H/src.Height);
      int dw=(int)Math.Round(src.Width*scale),dh=(int)Math.Round(src.Height*scale);
      g.DrawImage(src,new Rectangle((W-dw)/2,(H-dh)/2,dw,dh),0,0,src.Width,src.Height,GraphicsUnit.Pixel);
     }
     if(f==0) bmp.Save(Path.Combine(folder,"preview.png"),ImageFormat.Png);
     int offset=256+f*FrameBytes;
     for(int y=0;y<H;y++) for(int x=0;x<W;x++) {Color c=bmp.GetPixel(x,y); int v=((c.R>>3)<<11)|((c.G>>2)<<5)|(c.B>>3); data[offset++]=(byte)v;data[offset++]=(byte)(v>>8);}
    }
    manifest.AppendFormat("{0},{1},{2}\r\n",f,first,ticks*20);
   }
   File.WriteAllBytes(Path.Combine(folder,"animation.aula-rgb565"),data);
   File.WriteAllText(Path.Combine(folder,"frames.csv"),manifest.ToString());
   string info=String.Format("Source: {0}x{1}, {2} frames, {3} ms\r\nOutput: 240x135, {4} frames, {5} ms, {6} pages, {7} bytes\r\n",src.Width,src.Height,n,originalMs,count,emitted*20,data.Length/4096,data.Length);
   File.WriteAllText(Path.Combine(folder,"info.txt"),info);Console.WriteLine(info);return data;
  }
 }
 static void Validate(byte[] data) {
  if(data.Length<4096 || data.Length%4096!=0) throw new Exception("Invalid page alignment");
  int n=data[0]; if(n<1 || n>MaxFrames || data.Length!=((256+n*FrameBytes+4095)/4096)*4096) throw new Exception("Invalid frame count or size");
  for(int i=1;i<=n;i++) if(data[i]==0) throw new Exception("Invalid zero delay");
  for(int i=n+1;i<256;i++) if(data[i]!=255) throw new Exception("Invalid header padding");
 }
 static void Feature(SafeFileHandle h,byte command,int pages) {
  byte[] b=new byte[65];b[1]=4;b[2]=command;
  if(command==0x72) {b[3]=1;b[9]=(byte)pages;b[10]=(byte)(pages>>8);}
  if(!HidD_SetFeature(h,b,b.Length)) throw Win("Send command "+command.ToString("X2"));
  Thread.Sleep(35);
  if(!HidD_GetFeature(h,b,b.Length)) throw Win("Read command acknowledgment");
  if(b[1]!=4 || b[2]!=command || b[4]!=1) throw new Exception("Unexpected command ACK: "+BitConverter.ToString(b,0,12));
  Thread.Sleep(35);
 }
 static byte[] Transfer(SafeFileHandle h,byte[] data,bool write) {
  using(var ev=new EventWaitHandle(false,EventResetMode.ManualReset)) {
   IntPtr buffer=Marshal.AllocHGlobal(data.Length),ov=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Overlapped)));
   try {
    Marshal.Copy(data,0,buffer,data.Length); var o=new Overlapped();o.Event=ev.SafeWaitHandle.DangerousGetHandle();Marshal.StructureToPtr(o,ov,false);
    uint done;bool ok=write?WriteFile(h,buffer,(uint)data.Length,out done,ov):ReadFile(h,buffer,(uint)data.Length,out done,ov);
    if(!ok) {if(Marshal.GetLastWin32Error()!=997) throw Win(write?"Write page":"Read page ACK");
     if(!ev.WaitOne(5000)) {CancelIoEx(h,ov);GetOverlappedResult(h,ov,out done,true);throw new TimeoutException("USB transfer timed out; not retrying partial upload.");}
     if(!GetOverlappedResult(h,ov,out done,false)) throw Win("Finish USB transfer");
    }
    if(done!=data.Length) throw new Exception("Incomplete USB report: "+done);
    if(!write) Marshal.Copy(buffer,data,0,data.Length);return data;
   } finally {Marshal.FreeHGlobal(ov);Marshal.FreeHGlobal(buffer);}
  }
 }
 static void Upload(byte[] data) {
  Validate(data);var devices=Devices();Device control=null,screen=null;int controls=0,screens=0;
  foreach(var d in devices) {if(d.caps.page==0xff13 && d.caps.feature==65) {control=d;controls++;} if(d.caps.page==0xff68 && d.caps.output==4097 && d.caps.input==65) {screen=d;screens++;}}
  if(controls!=1 || screens!=1) throw new Exception("Expected exactly one F108 Pro with matching screen/control descriptors; found "+controls+" / "+screens);
  using(var c=CreateFile(control.path,0xc0000000,3,IntPtr.Zero,3,0,IntPtr.Zero))
  using(var s=CreateFile(screen.path,0xc0000000,3,IntPtr.Zero,3,0x40000000,IntPtr.Zero)) {
   if(c.IsInvalid || s.IsInvalid) throw Win("Open keyboard for upload");
   int pages=data.Length/4096;Console.WriteLine("Uploading {0} frames. Keep the cable connected.",data[0]);
   Feature(c,0x18,0);Feature(c,0x72,pages);
   for(int p=0;p<pages;p++) {
    byte[] report=new byte[4097];Buffer.BlockCopy(data,p*4096,report,1,4096);Transfer(s,report,true);
    byte[] ack=Transfer(s,new byte[65],false);
    if(ack[1]!=1 || ack[2]!=0x5a || ack[3]!=2) throw new Exception("Unexpected page ACK at "+p+": "+BitConverter.ToString(ack,0,12));
    if(p%100==0 || p==pages-1) Console.WriteLine("Progress: {0}/{1} ({2}%)",p+1,pages,(p+1)*100/pages);
   }
   Feature(c,0x02,0);Console.WriteLine("All pages acknowledged; APPLY acknowledged. Wait for the keyboard loading bar to finish.");
  }
 }
 [STAThread] static int Main(string[] args) {
  try {
   if(args.Length==0) {
    using(var pick=new OpenFileDialog()) {
     pick.Title="Select GIF for AULA F108 Pro";pick.Filter="GIF animation|*.gif";
     if(pick.ShowDialog()!=DialogResult.OK) return 0;
     string folder=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"converted",DateTime.Now.ToString("yyyyMMdd-HHmmss-fff"));
     byte[] converted=ConvertGif(pick.FileName,folder);Validate(converted);
     if(MessageBox.Show("Prepared "+converted[0]+" frames for 240 x 135.\nThis replaces the custom animation on your F108 Pro.\nConnect USB and select wired mode. Keep the cable connected during upload and until the keyboard loading bar finishes.\n\nUpload now?","AULA GIF",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes) return 0;
     Upload(converted);MessageBox.Show("Upload acknowledged. Wait for the keyboard loading bar to finish, then open GIF Image on the keyboard.","AULA GIF");return 0;
    }
   }
   if(args[0]=="list") {var ds=Devices();foreach(var d in ds) Console.WriteLine("F108 Pro usage=0x{0:X4}, input={1}, output={2}, feature={3}",d.caps.page,d.caps.input,d.caps.output,d.caps.feature);Console.WriteLine("Interfaces: "+ds.Count);}
   else if(args[0]=="convert" && args.Length==3) ConvertGif(args[1],args[2]);
   else if(args[0]=="upload" && args.Length==2) Upload(File.ReadAllBytes(args[1]));
   else if(args[0]=="check" && args.Length==2) {Validate(File.ReadAllBytes(args[1]));Console.WriteLine("Validated frame count, exact size, delay bytes, and header padding.");}
   else throw new Exception("Invalid arguments");return 0;
  } catch(Exception e) {Console.Error.WriteLine("ERROR: "+e.Message);if(args.Length==0) MessageBox.Show(e.Message,"AULA GIF error",MessageBoxButtons.OK,MessageBoxIcon.Error);return 1;}
 }
}
