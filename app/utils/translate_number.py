class TranslateNumber:
    class Numbers:
        def __init__(self, index, name):
            self.Index = index
            self.Name = name

    def __init__(self):
        self.numbersList = [
            self.Numbers(0, "zero"),
            self.Numbers(1, "jeden"),
            self.Numbers(2, "dwa"),
            self.Numbers(3, "trzy"),
            self.Numbers(4, "cztery"),
            self.Numbers(5, "pięć"),
            self.Numbers(6, "sześć"),
            self.Numbers(7, "siedem"),
            self.Numbers(8, "osiem"),
            self.Numbers(9, "dziewięc"),
            self.Numbers(10, "dziesięć"),
            self.Numbers(11, "jedenaście"),
            self.Numbers(12, "dwanaście"),
            self.Numbers(13, "trzynaście"),
            self.Numbers(14, "czternaście"),
            self.Numbers(15, "pietnaście"),
            self.Numbers(16, "szesnaście"),
            self.Numbers(17, "siedemaście"),
            self.Numbers(18, "osiemnaście"),
            self.Numbers(19, "dziewietnaście"),
            self.Numbers(20, "dwadzieścia"),
            self.Numbers(30, "trzydzieści"),
            self.Numbers(40, "czterdzieści"),
            self.Numbers(50, "pięćdziesiąt"),
            self.Numbers(60, "sześćdziesiąt"),
            self.Numbers(70, "siedemdziesiąt"),
            self.Numbers(80, "osiemdziesiąt"),
            self.Numbers(90, "dziewięćdziesiąt"),
            self.Numbers(100, "sto"),
            self.Numbers(200, "dwieście"),
            self.Numbers(300, "trzysta"),
            self.Numbers(400, "czterysta"),
            self.Numbers(500, "pięćset"),
            self.Numbers(600, "sześćset"),
            self.Numbers(700, "siedemset"),
            self.Numbers(800, "osiemset"),
            self.Numbers(900, "dziewięćset"),
            self.Numbers(1000, "tysiąc"),
            self.Numbers(2000, "dwa tysiące"),
            self.Numbers(3000, "trzy tysiące"),
            self.Numbers(4000, "cztery tysiące"),
            self.Numbers(5000, "pięć tysięcy"),
            self.Numbers(6000, "sześć tysięcy"),
            self.Numbers(7000, "siedem tysięcy"),
            self.Numbers(8000, "osiem tysięcy"),
            self.Numbers(9000, "dziewięć tysięcy"),
        ]

    def get_translation(self, number: str) -> str:
        s = int(number)
        length = len(number)

        if length == 1:
            return self.one_digit(s)
        elif length == 2:
            return self.two_digits(s)
        elif length == 3:
            return self.three_digits(s)
        elif length == 4:
            return self.four_digits(s)
        elif length == 5:
            return self.five_digits(s)
        return ""

    def query_number(self, input_number):
        for item in self.numbersList:
            if item.Index == input_number:
                return item.Name
        return ""

    def one_digit(self, num):
        return self.query_number(num)

    def two_digits(self, num):
        first, second = divmod(num, 10)
        if first == 1:
            return self.query_number(num)
        result = self.query_number(first * 10)
        if second > 0:
            result += f" {self.query_number(second)}"
        return result

    def three_digits(self, num):
        first = num // 100
        second = num % 100
        result = ""
        if 1 <= first <= 9:
            result = self.query_number(first * 100)
            if 1 <= second <= 99:
                result += f" {self.two_digits(second)}" if second > 9 else f" {self.one_digit(second)}"
        return result

    def four_digits(self, num):
        first = num // 1000
        second = num % 1000
        if 1 <= first <= 9:
            result = self.query_number(first * 1000)
            if second == 0:
                return result
            elif 1 <= second <= 9:
                return result + " " + self.one_digit(second)
            elif 10 <= second <= 99:
                return result + " " + self.two_digits(second)
            elif 100 <= second <= 999:
                return result + " " + self.three_digits(second)
        return ""

    def five_digits(self, num):
        first = num // 1000
        second = num % 1000
        if 1 <= first <= 99:
            result = self.two_digits(first) + " tysięcy"
            if second == 0:
                return result
            elif 1 <= second <= 9:
                return result + " " + self.one_digit(second)
            elif 10 <= second <= 99:
                return result + " " + self.two_digits(second)
            elif 100 <= second <= 999:
                return result + " " + self.three_digits(second)
        return ""
