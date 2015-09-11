contract LotteryAgent {

    uint golem_dep;

    struct LotteryData {
        uint value;
        uint maturity;
        uint deadline;
        uint winnerDeposit;
        uint payerDeposit;
        uint seed;
        address payer;
        address agent;
        address winner;
    }

    mapping (bytes32 => LotteryData) lotteries;

    function initLottery(bytes32 descriptionHash, uint maturity, uint deposit) {
        LotteryData lottery = lotteries[descriptionHash];
        if (lottery.value != 0)
            return;
        uint payerDeposit = msg.value / 10;
        uint value = msg.value - payerDeposit;
        lotteries[descriptionHash] = LotteryData(value, maturity, 0, deposit, payerDeposit, 0, msg.sender, 0, 0);
    }

    function captureMaturityHash(bytes32 descriptionHash) {
        LotteryData lottery = lotteries[descriptionHash];
        if (lottery.value == 0)
            return;

        if (lottery.seed != 0 )
            return;

        if (block.number <= lottery.maturity || block.number > lottery.maturity + 256)
            return;

        address sendTo = lottery.payer;
        if (lottery.maturity + 128 < block.number)
            sendTo = msg.sender;

       lottery.seed = random(lottery.maturity);
       sendTo.send(lottery.payerDeposit);
       lottery.payerDeposit = 0;
    }

    function winnerLottery(bytes32 descriptionHash) {
        LotteryData lottery = lotteries[descriptionHash];
        if (lottery.value == 0 || msg.value < lottery.payerDeposit)
            return;
        if (lottery.winner != 0 && block.number <= lottery.maturity) {
            return;
        }
        lottery.winnerDeposit = msg.value;
        lottery.winner = msg.sender;
        lottery.deadline = now + 86400;

        if (lottery.seed == 0) {
            lottery.seed = random(lottery.maturity);
            if (block.number <= lottery.maturity + 128)
                lottery.payer.send(lottery.payerDeposit);
            else if (block.number <= lottery.maturity + 256)
                msg.sender.send(lottery.payerDeposit);
            else
               golem_dep += lottery.payerDeposit;

            lottery.payerDeposit = 0;
        }

    }

    function otherWinnerLottery(bytes32 descriptionHash, address winner) {
        LotteryData lottery = lotteries[descriptionHash];
        if (lottery.value == 0 || msg.value < lottery.payerDeposit)
            return;
        if (lottery.winner != 0 && block.number <= lottery.maturity + 28800) {
            return;
        }
        lottery.winnerDeposit = msg.value;
        lottery.winner = winner;
        lottery.agent = msg.sender;
        lottery.deadline = now + 86400;

        if (lottery.seed == 0) {
            lottery.seed = random(lottery.maturity);
            golem_dep += lottery.payerDeposit;

            lottery.payerDeposit = 0;
        }

    }

    function payoutLottery(bytes32 descriptionHash) {
        LotteryData lottery = lotteries[descriptionHash];
        if (lottery.value == 0 || lottery.winner == 0)
            return;
        if (block.timestamp <= lottery.deadline)
            return;

        if (lottery.agent == 0) {
            lottery.winner.send(lottery.value + lottery.winnerDeposit);
        } else {
            uint val = lottery.value / 10;
            lottery.agent.send(val + lottery.winnerDesposit);
            lottery.winner.send(lottery.value - val);
        }
        delete lotteries[descriptionHash];
    }

    function checkLottery(uint maturity, uint lotteryId, uint startValue, address[] participants, uint[] probabilities) external {
        bytes32 descriptionHash = sha3(maturity, lotteryId, startValue, participants, probabilities);
        LotteryData lottery = lotteries[descriptionHash];
        if (lottery.value == 0 || block.number <= lottery.maturity)
            return;

        if (lottery.seed == 0) {
            lottery.seed = random(lottery.maturity);
            if (block.number <= lottery.maturity + 128)
                lottery.payer.send(lottery.payerDeposit);
            else if (block.number <= lottery.maturity + 256)
                msg.sender.send(lottery.payerDeposit);
            else
                golem_dep += lottery.payerDeposit;
            lottery.payerDeposit = 0;
        }

        address winner;
        uint target = 0;
        for (uint i = 0; i < probabilities.length; ++i) {
            target += probabilities[i];
            if (lottery.seed <= target) {
                winner = participants[i];
                break;
            }
        }


        if (lottery.winner == 0) {
            winner.send(lottery.value);
        } else {
            if (lottery.winner != winner) {
                uint val = lottery.winnerDeposit / 2;
                lottery.winnerDeposit = lottery.winnerDeposit - val;
                golem_dep += val;
            } else {
                if (lottery.agent ! = 0) {
                    uint val = lottery.value / 10;
                    lottery.agent.send(val);
                    lottery.value -= val;
                }

            }

            if (winner != msg.sender) {
                winner.send(lottery.value);
                msg.sender.send(lottery.winnerDeposit);
            } else {
                winner.send(lottery.value + lottery.winnerDeposit);
            }
        }
        delete lotteries[descriptionHash];

    }

    function random(uint maturity) internal constant returns(uint) {
        while (block.number - maturity > 256) {
            maturity += 256;
        }

        return uint(block.blockhash(maturity));
    }

    function verifyLottery(bytes32 descriptionHash) returns (bool) {
        return lotteries[descriptionHash].value != 0;
    }
}
