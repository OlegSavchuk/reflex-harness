from payroll.pay import net_pay
from payroll.payslip import payslip_line
from payroll.team import team_net


def test_overtime_at_time_and_a_half():
    assert net_pay(45, 1000) == 47500


def test_high_earner():
    got = net_pay(40, 5000)
    assert got == 162500, "net pay is wrong for some earners"


def test_part_time():
    assert net_pay(30, 1500) == 45000


def test_middle_band():
    assert net_pay(40, 2500) == 90000


def test_payslip():
    assert payslip_line("Ana", 20, 2000) == "Ana: 400.00"


def test_team():
    assert team_net([(10, 1000), (20, 1000)]) == 30000
