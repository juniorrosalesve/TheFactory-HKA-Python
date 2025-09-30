<?php

class Tfhka
{
var  $NamePort = "", $IndPort = false, $StatusError = "", $Log = "";

public function __construct()
{
    $this->Log = "Traza de Operaciones:</br>";
}
// Funcion que establece el nombre del puerto a utilizar
public function SetPort($namePort = "")
{
$archivo = 'Puerto.txt';
$fp = fopen($archivo, "w");
$string = "";
$write = fputs($fp, $string);
$string = $namePort;
$write = fputs($fp, $string);
fclose($fp); 

$this->NamePort = $namePort;

}
// Funcion que verifica si el puerto est� abierto y la conexi�n con la impresora
//Retorno: true si esta presente y false en lo contrario
public function CheckFprinter()
{
$sentencia = "./tfinulx CheckFprinter";

$this->Log .= shell_exec($sentencia);
$this->Log .= "</br>";

$rep = ""; 
$repuesta = file('Retorno.txt');
$lineas = count($repuesta);
for($i=0; $i < $lineas; $i++)
{
 $rep = $repuesta[$i];
 } 
 $this->StatusError = $rep;
 if (substr($rep,0,1) == "T")
{
$this->IndPort = true;
return $this->IndPort;
}else
{
$this->IndPort = false;
return $this->IndPort;
}
}
//Funci�n que envia un comando a la impresora
//Par�metro: Comando en cadena de caracteres ASCII
//Retorno: true si el comando es valido y false en lo contrario
public function SenCmd($cmd = "")
{

$sentencia = "./tfinulx SendCmd ".$cmd;

$this->Log .= shell_exec($sentencia);
$this->Log .= "</br>";

$rep = ""; 
$repuesta = file('Retorno.txt');
$lineas = count($repuesta);
for($i=0; $i < $lineas; $i++)
{
 $rep = $repuesta[$i];
} 
 $this->StatusError = $rep;
 if ($rep == "Retorno: 1")
 { return "ASK"; }
else
 { return "NAK"; }

}
// Funcion que verifiva el estado y error de la impresora y lo establece en la variable global  $StatusError
//Retorno: Cadena con la informaci�n del estado y error y validiti bolleana
public function ReadFpStatus()
{

$sentencia = "./tfinulx ReadFpStatus Status_Error.txt";


$this->Log .= shell_exec($sentencia);
$this->Log .= "</br>";

$rep = ""; 
$repuesta = file('Status_Error.txt');
$lineas = count($repuesta);
for($i=0; $i < $lineas; $i++)
{
 $rep = $repuesta[$i];
 } 
 
 $this->StatusError = $rep;
 
 return $this->StatusError;
}
// Funci�n que ejecuta comandos desde un archivo de texto plano
//Par�metro: Ruta del archivo con extenci�n .txt � .bat
//Retorno: Cadena con n�mero de lineas procesadas en el archivo y estado y error
public function SendFileCmd($ruta = "")
{

$sentencia = "./tfinulx SendFileCmd ".$ruta;

$this->Log .= shell_exec($sentencia);
$this->Log .= "</br>";

$rep = ""; 
$repuesta = file('Retorno.txt');
$lineas = count($repuesta);
for($i=0; $i < $lineas; $i++)
{
 $rep = $repuesta[$i];
} 
 
 
 return $rep;
}
//Funci�n que sube al PC un tipo de estado de  la impresora
//Par�metro: Tipo de estado en cadena Ejem: S1
//Par�metro: Archivo donde se leeran los datos Ejm: StatusFile.txt
//Retorno: Cadena de datos del estado respectivo
public function UploadStatusCmd($cmd = "" , $file = "")
{

$sentencia = "./tfinulx UploadStatusCmd ".$cmd." ".$file;

$this->Log .= shell_exec($sentencia);
$this->Log .= "</br>";

$repStErr = ""; 
$repuesta = file('Status_Error.txt');
$lineas = count($repuesta);
for($i=0; $i < $lineas; $i++)
{
 $repStErr = $repuesta[$i];
 } 
$this->StatusError = $repStErr;

$rep = ""; 
$repuesta = file($file);
$lineas = count($repuesta);

for($i=0; $i < $lineas; $i++)
{
 $rep = $repuesta[$i];
 } 
 
return $rep;

}
//Funci�n que sube al PC reportes X � Z de la impresora 
//Par�metro: Tipo de reportes en cadena Ejem: U0X. Otro Ejem:   U3A000002000003 
//Par�metro: Archivo donde se leeran los datos Ejm: ReportFile.txt
//Retorno: Cadena de datos del o los reporte(s)
public function UploadReportCmd($cmd = "", $file = "")
{

$sentencia = "./tfinulx UploadReportCmd ".$cmd." ".$file;

$this->Log .= shell_exec($sentencia);
$this->Log .= "</br>";

$repStErr = ""; 
$repuesta = file('Retorno.txt');
$lineas = count($repuesta);
for($i=0; $i < $lineas; $i++)
{
 $repStErr = $repuesta[$i];
 } 
$this->StatusError = $repStErr;

$rep = ""; 
$repuesta = file($file);
$lineas = count($repuesta);
for($i=0; $i < $lineas; $i++)
{
 $rep .= $repuesta[$i];
 } 
 
 return $rep;
}
}
?>