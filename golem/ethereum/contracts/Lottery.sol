contract Lottery {
    uint constant public maturity = 10; // blocks

    address public owner;
    uint public ownerDeposit; // golem account for commissions

    function Lottery() {
        owner = msg.sender;
    }

    // Lottery data.
    // OPT: This can be compressed to 2 words:
    //      - maturity can be uint64, also consider using lottery init stamp,
    //      - not all data is needed in the same time.
    struct LotteryData {
        uint value;
        uint maturity;
        uint32 randVal;
        address payer;
    }

    struct WinnerProof {
        uint256 uid; // lottery id
        address winner; // winner’s address
        uint32 rangeStart; // beginning of the range
        uint32 rangeLength; // length of the range
        bytes32[] values; // values w1, . . . , wd
    }

    mapping (bytes32 => LotteryData) lotteries;

    // Initialize a lottery by depositing its value in the contract.
    // TODO: Consider renaming it to deposit().
    function init(bytes32 lotteryHash) external {
        var lottery = lotteries[lotteryHash];
        if (lottery.value != 0)
            return;  // TODO: Here the sender looses his money. What should we do with it?

        // TODO: What if value is 0?
        uint payerDeposit = calculateInitialPayerDeposit(msg.value);
        lottery.value = msg.value - payerDeposit;
        lottery.maturity = block.number + maturity;
        lottery.payer = msg.sender;
    }

    function getValue(bytes32 lotteryHash) external constant returns (uint) {
        return lotteries[lotteryHash].value;
    }

    function getMaturity(bytes32 lotteryHash) external constant returns (uint) {
        return lotteries[lotteryHash].maturity;
    }

    function getRandomValue(bytes32 lotteryHash) external constant returns (uint32) {
        return lotteries[lotteryHash].randVal;
    }

    // Validates the lottery winner using attached proof. If valid, the reward
    // is payed out to the winner.
    function check(bytes32 lotteryHash, uint256 uid, address winner, uint32 rangeStart,
                   uint32 rangeLength, bytes32[] values) external {
        var proof = WinnerProof(uid, winner, rangeStart, rangeLength, values);
        var lottery = lotteries[lotteryHash];
        if (lottery.value == 0 || block.number <= lottery.maturity)
            return;
        if (lottery.randVal == 0) // OPT: This check might not be needed
            randomize(lotteryHash);
        if (!validateProof(lottery.randVal, lotteryHash, proof))
            return;

        // Payout the reward.
        // In case send fails we allow rechecking in future.
        // Becouse msg.sender may not be the winner, this prevents attacks
        // on a winner being a contract.
        if (winner.send(lottery.value))
            delete lotteries[lotteryHash];
    }

    // Fetch and set a random value for a given lottery.
    function randomize(bytes32 lotteryHash) {
        var lottery = lotteries[lotteryHash];

        // Check if the lottery maturity has been reached.
        if (block.number <= lottery.maturity)
            return;

        // Do not allow reseting random value.
        if (lottery.randVal != 0)
            return;

        // Find the receiver of randomization reward.
        address randomizer;
        // The lottery payer can get back its deposit.
        if (block.number <= lottery.maturity + 128)
            randomizer = lottery.payer;
        // Otherwise anyone can get the reward.
        else if (block.number <= lottery.maturity + 256)
            randomizer = msg.sender;

        // Sent the reward if possible. Otherwise the owner gets the reward.
        var reward = calculatePayerDeposit(lottery.value);
        if (randomizer == 0 || !randomizer.send(reward))
            ownerDeposit += reward;

        // Set the random value and clear unneed data.
        lottery.randVal = random(lottery.maturity);
        lottery.maturity = 0;
        lottery.payer = 0;
    }

    function validateProof(uint32 rand, bytes32 lotteryHash, WinnerProof proof) internal returns (bool) {
        // Check if random val falls into the range
        if (rand < proof.rangeStart || rand > proof.rangeStart + proof.rangeLength - 1) // FIXME: Check overflows, length == 0
            return false;
        // Initially, h is the value stored in the leaf (hd)
        bytes32 h = sha3(proof.winner, proof.rangeStart, proof.rangeLength);
        // Update h with hashes hd−1, ... , h0
        for (uint i = 0; i < proof.values.length; ++i)
            h = sha3(h ^ proof.values[i]);
        // Mix with uid
        h = sha3(proof.uid, h);
        return h == lotteryHash;
    }

    function changeMaturity(uint maturity) internal constant returns(uint) {
        uint begMod = (block.number - 256) % 256;
        uint matMod = maturity % 256;
        maturity = (block.number - 256) + matMod - begMod;
        if (begMod > matMod)
            maturity += 256;
        return maturity;
    }

    function random(uint maturity) internal constant returns(uint32) {
        if (block.number - maturity > 256)
            maturity = changeMaturity(maturity);
        return uint32(block.blockhash(maturity));
    }

    function calculateInitialPayerDeposit(uint val) internal constant returns (uint) {
        return val / 11;
    }
    function calculatePayerDeposit(uint val) internal constant returns (uint) {
        return val / 10;
    }

    function getOwnerDeposit() external constant returns (uint) {
        return ownerDeposit;
    }

    function payout() {
        if (owner.send(ownerDeposit))
            ownerDeposit = 0;
    }
}
