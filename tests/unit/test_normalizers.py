"""Tests unitarios (TDD) para la capa de normalización y sanitización contable (SPEC-017)."""

from src.reporting.normalizers import (
    normalize_bank_name,
    normalize_cedula,
    normalize_phone,
    normalize_reference,
    normalize_text,
    parse_monetary_amount,
)


def test_normalize_text_basic():
    assert normalize_text(None) == ""
    assert normalize_text("") == ""
    assert normalize_text("   hola   mundo   ") == "HOLA MUNDO"
    assert normalize_text("pago móvil con éxito y liquidación") == "PAGO MOVIL CON EXITO Y LIQUIDACION"
    assert normalize_text("año nuevo") == "ANO NUEVO"


def test_normalize_bank_name():
    assert normalize_bank_name(None) == "BANCO DESCONOCIDO"
    assert normalize_bank_name("") == "BANCO DESCONOCIDO"
    assert normalize_bank_name("Banco de Venezuela, S.A.") == "BANCO DE VENEZUELA"
    assert normalize_bank_name("bdv en linea") == "BANCO DE VENEZUELA"
    assert normalize_bank_name("banesco banco universal") == "BANESCO"
    assert normalize_bank_name("Banesco") == "BANESCO"
    assert normalize_bank_name("Mercantil Banco Universal") == "MERCANTIL"
    assert normalize_bank_name("bbva provincial") == "PROVINCIAL"
    assert normalize_bank_name("Bancamiga Banco Universal") == "BANCAMIGA"
    assert normalize_bank_name("BNC") == "BNC"
    assert normalize_bank_name("Banco Nacional de Crédito") == "BNC"
    assert normalize_bank_name("Bancaribe C.A.") == "BANCARIBE"
    assert normalize_bank_name("Banco Plaza") == "BANCO PLAZA"


def test_normalize_cedula():
    assert normalize_cedula(None) == "S/C"
    assert normalize_cedula("") == "S/C"
    assert normalize_cedula("v- 19.456.789 ") == "V-19456789"
    assert normalize_cedula("V18234567") == "V-18234567"
    assert normalize_cedula("j- 12345678-0") == "J-123456780"
    assert normalize_cedula("E-84.111.222") == "E-84111222"
    assert normalize_cedula("G20001234") == "G-20001234"
    assert normalize_cedula("sin cedula") == "S/C"


def test_normalize_phone():
    assert normalize_phone(None) == "N/A"
    assert normalize_phone("") == "N/A"
    assert normalize_phone("+58 414 123 4567") == "0414-1234567"
    assert normalize_phone("584249988776") == "0424-9988776"
    assert normalize_phone("04121234567") == "0412-1234567"
    assert normalize_phone("4165556677") == "0416-5556677"
    assert normalize_phone("123") == "N/A"


def test_normalize_reference():
    assert normalize_reference(None) == "S/R"
    assert normalize_reference("") == "S/R"
    assert normalize_reference("REF: 000849201") == "000849201"
    assert normalize_reference("Transf. # 94821038") == "94821038"
    assert normalize_reference("01928374") == "01928374"
    assert normalize_reference("   884921   ") == "884921"


def test_parse_monetary_amount():
    assert parse_monetary_amount(None) == 0.0
    assert parse_monetary_amount("") == 0.0
    assert parse_monetary_amount(2500) == 2500.0
    assert parse_monetary_amount(1500.75) == 1500.75
    # Notación venezolana / europea (coma decimal)
    assert parse_monetary_amount("Bs. 2.450,50") == 2450.50
    assert parse_monetary_amount("1500,50") == 1500.50
    assert parse_monetary_amount("Bs 1.500.000,00") == 1500000.00
    # Notación internacional (punto decimal)
    assert parse_monetary_amount("5120.50") == 5120.50
    assert parse_monetary_amount("1,500.50") == 1500.50
    assert parse_monetary_amount("$ 3,500.00 USDT") == 3500.00
    # Enteros
    assert parse_monetary_amount("1000") == 1000.00
    assert parse_monetary_amount("Bs. 1000") == 1000.00
    # Casos inválidos
    assert parse_monetary_amount("abc") == 0.0
