from twocaptcha import TwoCaptcha

solver = TwoCaptcha('f217d224489ed89ae7fd0823275b3a58')

def solve_captcha(gt: str, challenge: str):

    try:
        result = solver.geetest(gt=gt,
                                challenge=challenge,
                                url='https://marketplace.axieinfinity.com/')
        return result
    except:
        print("Something happened with the captcha solver, please contact support.\n")
        return None
