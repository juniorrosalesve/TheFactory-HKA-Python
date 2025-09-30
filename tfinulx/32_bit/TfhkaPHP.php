<?php

class Tfhka
{
var  $NamePort = "", $IndPort = false, $StatusError = "";

function Tfhka()
{
}
// Funcion que establece el nombre del puerto a utilizar
function SetPort($namePort = "")
{
$archivo = '/var/www/html/tfhka_php_linux/tfinulx/64 bit/Puerto.txt';
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
function CheckFprinter()
{
$sentencia = "./tfinulx CheckFprinter";

shell_exec($sentencia);

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
function SenCmd($cmd = "")
{

$sentencia = "./tfinulx SendCmd ".$cmd;

shell_exec($sentencia);

$rep = ""; 
$repuesta = file('/var/www/html/tfhka_php_linux/tfinulx/64 bit/Retorno.txt');
$lineas = count($repuesta);
for($i=0; $i < $lineas; $i++)
{
 $rep = $repuesta[$i];
 } 
 $this->StatusError = $rep;
 if (substr($rep,0,1) == "T")
return true;
else
return false;

}
// Funcion que verifiva el estado y error de la impresora y lo establece en la variable global  $StatusError
//Retorno: Cadena con la informaci�n del estado y error y validiti bolleana
function ReadFpStatus()
{

$sentencia = "./tfinulx ReadFpStatus status_error.txt";


shell_exec($sentencia);

$rep = ""; 
$repuesta = file('/var/www/html/tfhka_php_linux/tfinulx/64 bit/status_error.txt');
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
function SendFileCmd($ruta = "")
{

$sentencia = "./tfinulx SendFileCmd ".$ruta;

shell_exec($sentencia);

$rep = ""; 
$repuesta = file('/var/www/html/tfhka_php_linux/tfinulx/64 bit/Retorno.txt');
$lineas = count($repuesta);
for($i=0; $i < $lineas; $i++)
{
 $rep = $repuesta[$i];
 } 
 
 
 return $rep;
}
//Funci�n que sube al PC un tipo de estado de  la impresora
//Par�metro: Tipo de estado en cadena Ejem: S1
//Retorno: Cadena de datos del estado respectivo
function UploadStatusCmd($cmd = "" , $file = "")
{

$sentencia = "./tfinulx UploadStatusCmd ".$cmd." ".$file;

shell_exec($sentencia);

$repStErr = ""; 
$repuesta = file('/var/www/html/tfhka_php_linux/tfinulx/64 bit/Status_Error.txt');
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
//Retorno: Cadena de datos del o los reporte(s)
function UploadReportCmd($cmd = "", $file = "")
{

$sentencia = "./tfinulx UploadReportCmd ".$cmd." ".$file;

exec($sentencia);

$repStErr = ""; 
$repuesta = file('/var/www/html/tfhka_php_linux/tfinulx/64 bit/Retorno.txt');
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