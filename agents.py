agent_list = [
    {
        "name": "Joon",
        "persona": "a curious 7th grader who loves math puzzles, but sometimes overlooks important details when canceling terms.",
        "task_schema": {
            "task 1": {
                "description": "Factorize the numerator m^2 + 2m - 3.",
                "variables": {
                    "numerator_expression": "m^2 + 2m - 3",
                    "factors_of_numerator": ["(m + 3)", "(m - 1)"],
                    "factorized_numerator": "(m + 3)(m - 1)"
                }
            },
            "task 2": {
                "description": "Identify the denominator and incorrectly assume it can be canceled with a similar term in the numerator.",
                "variables": {
                    "denominator_expression": "m - 3",
                    "numerator_factors": ["(m + 3)", "(m - 1)"],
                    "incorrect_cancellation_attempt": "Cancels (m + 3) and (m - 3)"
                }
            },
            "task 3": {
                "description": "Attempt to simplify the expression after incorrect cancellation.",
                "variables": {
                    "simplification_step": "Cancels (m + 3) with (m - 3) incorrectly",
                    "incorrect_simplified_expression": "(m - 1)"
                }
            },
            "task 4": {
                "description": "Identify the answer based on the incorrect simplification.",
                "variables": {
                    "correct_answer": "m - 1"
                }
            }
        }
     },
    {
        "name": "Carolyn",
        "persona": "an enthusiastic 8th grader who likes to solve math problems in steps.",
        "task_schema": {
            "task 1": {
                "description": "Factorize the numerator m^2 + 2m - 3.",
                "variables": {
                    "numerator_expression": "m^2 + 2m - 3",
                    "factors_of_numerator": ["(m - 3)", "(m - 1)"],
                    "factorized_numerator": "(m - 3)(m - 1)"
                }
            },
            "task 2": {
                "description": "Identify the denominator and check if it shares any common factors with the numerator.",
                "variables": {
                    "denominator_expression": "m - 3",
                    "numerator_factors": ["(m - 3)", "(m - 1)"],
                    "common_factor_found": "Yes"
                }
            },
            "task 3": {
                "description": "Determine if the expression can be simplified by canceling out common factors between the numerator and denominator.",
                "variables": {
                    "simplification_step": "m - 3",
                    "simplified_expression": "Does simplify"
                }
            },
            "task 4": {
                "description": "Identify the correct answer based on the simplification result.",
                "variables": {
                    "correct_answer": "m - 1"
                }
            }
        }
    },
    # {
    #     "name": "Helena",
    #     "persona": "a 7th grader who enjoys explaining math solutions to her classmates.",
    #     "task_schema": {
    #         "task 1": {
    #             "description": "Factorize the numerator m^2 + 2m - 3.",
    #             "variables": {
    #                 "numerator_expression": "m^2 + 2m - 3",
    #                 "factors_of_numerator": ["(m + 3)", "(m - 1)"],
    #                 "factorized_numerator": "(m + 3)(m - 1)"
    #             }
    #         },
    #         "task 2": {
    #             "description": "Identify the denominator and check if it shares any common factors with the numerator.",
    #             "variables": {
    #                 "denominator_expression": "m - 3",
    #                 "numerator_factors": ["(m + 3)", "(m - 1)"],
    #                 "common_factor_found": "No"
    #             }
    #         },
    #         "task 3": {
    #             "description": "Determine if the expression can be simplified by canceling out common factors between the numerator and denominator.",
    #             "variables": {
    #                 "simplification_step": "None, as there is no common factor.",
    #                 "simplified_expression": "Does not simplify"
    #             }
    #         },
    #         "task 4": {
    #             "description": "Identify the correct answer based on the simplification result.",
    #             "variables": {
    #                 "correct_answer": "D"
    #             }
    #         }
    #     }
    # },
    # {
    #     "name": "Michael",
    #     "persona": "a quiet but thoughtful 8th grader who checks details carefully.",
    #     "task_schema": {
    #         "task 1": {
    #             "description": "Factorize the numerator m^2 + 2m - 3.",
    #             "variables": {
    #                 "numerator_expression": "m^2 + 2m - 3",
    #                 "factors_of_numerator": ["(m + 3)", "(m - 1)"],
    #                 "factorized_numerator": "(m + 3)(m - 1)"
    #             }
    #         },
    #         "task 2": {
    #             "description": "Identify the denominator and check if it shares any common factors with the numerator.",
    #             "variables": {
    #                 "denominator_expression": "m - 3",
    #                 "numerator_factors": ["(m + 3)", "(m - 1)"],
    #                 "common_factor_found": "No"
    #             }
    #         },
    #         "task 3": {
    #             "description": "Determine if the expression can be simplified by canceling out common factors between the numerator and denominator.",
    #             "variables": {
    #                 "simplification_step": "None, as there is no common factor.",
    #                 "simplified_expression": "Does not simplify"
    #             }
    #         },
    #         "task 4": {
    #             "description": "Identify the correct answer based on the simplification result.",
    #             "variables": {
    #                 "correct_answer": "D"
    #             }
    #         }
    #     }
    # },
    # {
    #     "name": "Percy",
    #     "persona": "a 7th grader who is quick to spot patterns in math problems.",
    #     "task_schema": {
    #         "task 1": {
    #             "description": "Factorize the numerator m^2 + 2m - 3.",
    #             "variables": {
    #                 "numerator_expression": "m^2 + 2m - 3",
    #                 "factors_of_numerator": ["(m + 3)", "(m - 1)"],
    #                 "factorized_numerator": "(m + 3)(m - 1)"
    #             }
    #         },
    #         "task 2": {
    #             "description": "Identify the denominator and check if it shares any common factors with the numerator.",
    #             "variables": {
    #                 "denominator_expression": "m - 3",
    #                 "numerator_factors": ["(m + 3)", "(m - 1)"],
    #                 "common_factor_found": "No"
    #             }
    #         },
    #         "task 3": {
    #             "description": "Determine if the expression can be simplified by canceling out common factors between the numerator and denominator.",
    #             "variables": {
    #                 "simplification_step": "None, as there is no common factor.",
    #                 "simplified_expression": "Does not simplify"
    #             }
    #         },
    #         "task 4": {
    #             "description": "Identify the correct answer based on the simplification result.",
    #             "variables": {
    #                 "correct_answer": "D"
    #             }
    #         }
    #     }
    # }
]
